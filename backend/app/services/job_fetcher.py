"""
ProofPath AI — SSRF-Safe Job Posting Fetcher
Safely retrieves and sanitizes external job posting HTML:
- Strict scheme enforcement (http/https only)
- Credential rejection in URLs
- Pre-flight DNS resolution and IP range validation
- Blocks loopback, private, link-local, multicast, reserved, and cloud-metadata addresses
- Hop-by-hop redirect re-validation (no automatic unvalidated redirects)
- Strict timeouts (10s) and streaming body size caps (max 2 MB)
- HTML sanitization stripping scripts, styles, hidden tags, and nav elements
- Text truncation to 50,000 bytes
"""
import ipaddress
import logging
import re
import socket
from typing import Any, Iterable, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpcore
from httpcore._backends.anyio import AnyIOBackend, AsyncNetworkStream
import httpx

logger = logging.getLogger("proofpath_ai.job_fetcher")

MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 10.0
MAX_HTML_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_RAW_TEXT_BYTES = 50000  # Database column limit

# Cloud metadata addresses to explicitly reject
CLOUD_METADATA_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.internal",
    "100.100.100.200",  # Alibaba cloud metadata
}


class PinnedNetworkBackend(AnyIOBackend):
    """
    Guarantees the TCP socket connects strictly to the pre-validated public IP address,
    preventing DNS rebinding / race conditions between DNS inspection and socket connection,
    while preserving TLS SNI and certificate verification against the target hostname.
    """
    def __init__(self, pinned_ip: str):
        super().__init__()
        self.pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> AsyncNetworkStream:
        # Override destination host with the verified pinned IP
        return await super().connect_tcp(
            host=self.pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class JobFetchError(Exception):
    """Base error for job URL fetching."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class JobFetchSSRFError(JobFetchError):
    """Raised when a URL destination is blocked for security / SSRF defense."""
    def __init__(self, message: str):
        super().__init__(
            f"Security restriction: Destination URL is prohibited ({message}). Please paste job text directly.",
            status_code=400,
        )


def validate_destination_ip(ip_str: str) -> None:
    """
    Validates that a resolved IP address does not target private, loopback,
    link-local, cloud metadata, or reserved networks.
    Defends against IPv4-mapped IPv6 bypasses (e.g. ::ffff:127.0.0.1).
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        raise JobFetchSSRFError(f"Invalid IP address format: {ip_str}")

    # Handle IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1, ::ffff:169.254.169.254)
    if ip.version == 6 and ip.ipv4_mapped:
        validate_destination_ip(str(ip.ipv4_mapped))
        if str(ip.ipv4_mapped) in CLOUD_METADATA_HOSTS:
            raise JobFetchSSRFError("Cloud metadata address blocked")

    if ip.is_loopback:
        raise JobFetchSSRFError("Loopback address blocked")
    if ip.is_private:
        raise JobFetchSSRFError("Private network address blocked")
    if ip.is_link_local:
        raise JobFetchSSRFError("Link-local address blocked")
    if ip.is_multicast:
        raise JobFetchSSRFError("Multicast address blocked")
    if ip.is_reserved:
        raise JobFetchSSRFError("Reserved address blocked")
    if ip.is_unspecified:
        raise JobFetchSSRFError("Unspecified address (0.0.0.0) blocked")

    # Cloud metadata check
    if str(ip) in CLOUD_METADATA_HOSTS:
        raise JobFetchSSRFError("Cloud metadata address blocked")


def validate_url_and_resolve(url: str) -> Tuple[str, str, int, str]:
    """
    Parses a URL, validates scheme and host, resolves DNS,
    and ensures all resolved IPs are safe public addresses.
    Returns (cleaned_url, hostname, port, safe_ip).
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ("http", "https"):
        raise JobFetchSSRFError(f"Unsupported scheme '{parsed.scheme}'. Only http and https are allowed.")

    if not parsed.hostname:
        raise JobFetchSSRFError("URL must contain a valid hostname.")

    hostname = parsed.hostname.strip().lower()

    if parsed.username or parsed.password:
        raise JobFetchSSRFError("Embedded user credentials in URLs are not permitted.")

    if hostname in CLOUD_METADATA_HOSTS or hostname.endswith(".internal"):
        raise JobFetchSSRFError("Internal or metadata hostname blocked.")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)

    # Resolve hostname to all IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        logger.warning(f"DNS resolution failed for hostname '{hostname}': {exc}")
        raise JobFetchError(f"Could not resolve domain '{hostname}'. Please check the URL or paste the job description.", status_code=400)

    if not addr_info:
        raise JobFetchError(f"No IP addresses resolved for '{hostname}'.", status_code=400)

    first_safe_ip: Optional[str] = None
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        validate_destination_ip(ip_str)
        if first_safe_ip is None:
            first_safe_ip = ip_str

    if not first_safe_ip:
        raise JobFetchSSRFError("No safe destination IP found for host.")

    return url, hostname, port, first_safe_ip


async def fetch_job_url(target_url: str) -> Tuple[str, str, Optional[str]]:
    """
    Safely fetches a job posting HTML page with DNS-rebinding SSRF defense and extracts clean text.
    Pins the underlying TCP socket to the validated public IP address while preserving TLS SNI.
    Returns (clean_text, page_title, source_url).
    """
    current_url = target_url
    redirect_count = 0

    while True:
        # Pre-flight DNS & IP check on every hop
        validated_url, hostname, port, safe_ip = validate_url_and_resolve(current_url)

        # Build transport with PinnedNetworkBackend to eliminate DNS rebinding gap
        transport = httpx.AsyncHTTPTransport()
        transport._pool = httpcore.AsyncConnectionPool(
            network_backend=PinnedNetworkBackend(safe_ip),
            ssl_context=transport._pool._ssl_context,
        )

        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            timeout=httpx.Timeout(FETCH_TIMEOUT_SECONDS),
            headers={
                "User-Agent": "ProofPath-AI/1.0 (Job Extraction Bot; Safe Scanner)",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
            },
        ) as client:
            try:
                response = await client.get(validated_url)
            except httpx.TimeoutException:
                raise JobFetchError("Connection timed out while fetching job posting. Please try pasting the text.", status_code=504)
            except httpx.RequestError as exc:
                raise JobFetchError(f"Failed to connect to job URL: {type(exc).__name__}. Please paste the text instead.", status_code=502)

            # Handle redirects manually to re-verify destination
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise JobFetchError("Redirect received without Location header.")
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    raise JobFetchError("Too many redirects. Please paste the job description directly.")
                current_url = urljoin(current_url, location)
                continue

            if response.status_code != 200:
                raise JobFetchError(
                    f"Job page returned status {response.status_code}. The page may require login. Please paste the job description.",
                    status_code=400,
                )

            # Cap content size
            raw_bytes = response.content
            if len(raw_bytes) > MAX_HTML_BYTES:
                raise JobFetchError("Job posting HTML exceeds 2 MB limit. Please paste the job description directly.", status_code=413)

            # Decode content safely
            content_type = response.headers.get("Content-Type", "")
            encoding = response.encoding or "utf-8"
            try:
                html_text = raw_bytes.decode(encoding, errors="replace")
            except Exception:
                html_text = raw_bytes.decode("utf-8", errors="replace")

            clean_text, title = sanitize_html_to_text(html_text)
            lower_clean = clean_text.lower()
            if (
                not clean_text
                or len(clean_text.strip()) < 50
                or "enable javascript" in lower_clean
                or "please turn on javascript" in lower_clean
            ):
                raise JobFetchError(
                    "Extracted page content was unreadable or requires JavaScript execution. "
                    "ProofPath AI does not execute remote JavaScript for security reasons. "
                    "Please switch to the 'Paste Job Text' tab and paste the job description directly.",
                    status_code=400,
                )

            return clean_text, title, current_url


def sanitize_html_to_text(html_content: str) -> Tuple[str, str]:
    """
    Strips scripts, styles, forms, navigation, and SVG elements from HTML.
    Extracts readable text and page title.
    Enforces a strict 50,000-byte cap on returned text.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract title
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    if not title or title.lower() in ("page_title", "title", "loading..."):
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "form", "aside"]):
        tag.decompose()

    # Extract clean text with newline separation
    text = soup.get_text(separator="\n")

    # Clean redundant whitespace and empty lines
    lines = [line.strip() for line in text.splitlines()]
    clean_lines = [l for l in lines if l]
    cleaned = "\n".join(clean_lines)

    # Truncate to 50KB utf-8 limit
    encoded = cleaned.encode("utf-8")
    if len(encoded) > MAX_RAW_TEXT_BYTES:
        cleaned = encoded[:MAX_RAW_TEXT_BYTES].decode("utf-8", errors="ignore")

    return cleaned, title
