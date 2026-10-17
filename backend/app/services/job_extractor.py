"""
ProofPath AI — Deterministic Job Requirements Extraction Engine
Extracts structured competencies from job descriptions:
- Title and company detection
- Section segmentation (Required vs Preferred / Differentiators)
- Bullet and item parsing with context snippets
- Technology, language, and framework tagging
- Defense against prompt injection (pure deterministic lexical parsing; no LLM instruction execution)
- Fallback synthesis for unstructured or short postings
"""
import re
from typing import Dict, List, Optional, Tuple
from app.schemas.job import ExtractedRequirement

# Technology keywords and their canonical tags
TECH_KEYWORDS = {
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "python": "Python",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "c++": "C++",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "sql": "SQL",
    "mysql": "MySQL",
    "redis": "Redis",
    "mongodb": "MongoDB",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "sqs": "SQS",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "ci/cd": "CI/CD",
    "github actions": "CI/CD",
    "react": "React",
    "fastapi": "FastAPI",
    "node": "Node.js",
    "next.js": "Next.js",
    "opentelemetry": "OpenTelemetry",
    "otel": "OpenTelemetry",
    "graphql": "GraphQL",
    "rest": "REST API",
    "microservices": "Microservices",
    "concurrency": "Concurrency",
    "unit test": "Testing",
    "integration test": "Testing",
    "ebpf": "eBPF",
}

# Regex headers for required skills
CORE_SECTION_PATTERNS = [
    re.compile(r"(?i)^(?:requirements?|qualifications?|what you('ll| will) need|must have|minimum qualifications?|basic qualifications?|key requirements?|core skills?)"),
]

# Regex headers for preferred skills
PREFERRED_SECTION_PATTERNS = [
    re.compile(r"(?i)^(?:preferred|nice to have|bonus|differentiators?|plus(es)?|preferred qualifications?|desired skills?|what would make you stand out)"),
]


def extract_title_and_company(text: str, fallback_title: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Extracts job title and hiring company from the initial lines of the posting text.
    Guarantees title and company are always bound to avoid UnboundLocalError.
    """
    title: str = (fallback_title.strip() if fallback_title and fallback_title.strip() else "") or "Target Role"
    company: Optional[str] = None

    # Check if initial title has "Job Application for <Role> at <Company>"
    if fallback_title:
        app_match = re.search(r"(?i)Job Application for\s+(.+?)\s+at\s+(.+)", fallback_title)
        if app_match:
            title = app_match.group(1).strip()
            company = app_match.group(2).strip()

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return title, company

    for idx, line in enumerate(lines[:20]):
        # "Job Application for <Role> at <Company>" in body
        app_match = re.search(r"(?i)Job Application for\s+(.+?)\s+at\s+(.+)", line)
        if app_match:
            title = app_match.group(1).strip()
            company = app_match.group(2).strip()
            continue

        # Role / Title pattern: "Role: Backend Engineer" or "Title: Senior Go Developer"
        role_match = re.match(r"(?i)^(?:role|job title|position|title)\s*[:\-]\s*(.+)$", line)
        if role_match:
            title = role_match.group(1).strip()
            continue
        elif re.match(r"(?i)^(?:job title|role|position)\s*[:\-]?$", line) and idx + 1 < len(lines):
            title = lines[idx + 1].strip()
            continue

        # Company pattern: "Company: Applied Systems" or "About Sezzle:"
        comp_match = re.match(r"(?i)^(?:company|organization|at)\s*[:\-]\s*(.+)$", line)
        if comp_match:
            company = comp_match.group(1).strip()
            continue
        about_match = re.match(r"(?i)^about\s+([A-Za-z0-9_\-\s]{2,30})\s*[:\-]$", line)
        if about_match and not company:
            company = about_match.group(1).strip()
            continue

    # If title still generic, use the first non-empty line if it looks like a headline (< 80 chars)
    if title in ("Target Role", "page_title", "") and lines:
        for candidate_line in lines[:5]:
            if (
                len(candidate_line) < 80
                and not re.search(r"[:\d]", candidate_line)
                and candidate_line.lower() not in ("page_title", "back to jobs", "apply", "share", "overview")
            ):
                title = candidate_line
                break

    # Clean up and ensure fallback values
    title = title.strip() if title else "Target Job"
    if company:
        company = company.strip() or None

    return title, company


def extract_tags_from_text(text: str) -> List[str]:
    """
    Finds technology and architecture tags mentioned in a requirement snippet.
    """
    lower = text.lower()
    found_tags = set()
    for kw, tag in TECH_KEYWORDS.items():
        # Match as discrete word or token
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, lower):
            found_tags.add(tag)
    return sorted(list(found_tags))


def parse_job_requirements(
    raw_text: str,
    provenance: str = "user_pasted",
    initial_title: Optional[str] = None,
) -> Tuple[str, Optional[str], List[ExtractedRequirement]]:
    """
    Deterministically parses job description text into title, company, and structured requirements.
    Separates core required skills from preferred differentiators.
    """
    title, company = extract_title_and_company(raw_text, fallback_title=initial_title)

    lines = raw_text.splitlines()
    current_category = "core_required"
    current_section = "General Requirements"

    requirements: List[ExtractedRequirement] = []
    item_counter = 1

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Check for section headers
        cleaned_header = trimmed.rstrip(":")
        is_preferred = any(p.search(cleaned_header) for p in PREFERRED_SECTION_PATTERNS)
        is_core = any(p.search(cleaned_header) for p in CORE_SECTION_PATTERNS)

        if is_preferred:
            current_category = "preferred_differentiator"
            current_section = trimmed
            continue
        elif is_core:
            current_category = "core_required"
            current_section = trimmed
            continue

        # Check for bullet point lines or numbered items
        is_bullet = bool(re.match(r"^[\-\*•\+]\s+", trimmed) or re.match(r"^\d+[\.\)]\s+", trimmed))
        
        # If it's a bullet item or a standalone descriptive sentence inside a recognized section
        if is_bullet or (len(trimmed) > 20 and any(kw in trimmed.lower() for kw in TECH_KEYWORDS)):
            content = re.sub(r"^[\-\*•\+\d\.\)]+\s*", "", trimmed).strip()
            if len(content) < 8:
                continue

            tags = extract_tags_from_text(content)

            # Generate a clean concise skill name
            skill_name = content
            if len(content) > 70:
                # Truncate at first clause or sentence
                match = re.split(r"[,;.]\s", content)
                if match and len(match[0]) >= 15:
                    skill_name = match[0].strip()
                else:
                    skill_name = content[:67].strip() + "..."

            req_id = f"req_{item_counter:02d}"
            item_counter += 1

            requirements.append(
                ExtractedRequirement(
                    id=req_id,
                    skill_name=skill_name or "Technical Competency",
                    category=current_category,
                    description=content,
                    provenance=provenance,
                    tags=tags,
                    section_label=current_section,
                    is_included=True,
                    is_candidate_edited=False,
                )
            )

    # Fallback if no bullet points could be identified (e.g. plain text paragraph)
    if not requirements and len(raw_text.strip()) > 30:
        sentences = [s.strip() for s in re.split(r"[.\n]+", raw_text) if len(s.strip()) > 15]
        for idx, sentence in enumerate(sentences[:8], start=1):
            tags = extract_tags_from_text(sentence)
            if tags or idx <= 3:
                req_id = f"req_{item_counter:02d}"
                item_counter += 1
                requirements.append(
                    ExtractedRequirement(
                        id=req_id,
                        skill_name=sentence[:60] + ("..." if len(sentence) > 60 else ""),
                        category="core_required" if idx <= 4 else "preferred_differentiator",
                        description=sentence,
                        provenance=provenance,
                        tags=tags,
                        section_label="General Requirements",
                        is_included=True,
                        is_candidate_edited=False,
                    )
                )

    # Absolute fallback if still empty (ensures UI review screen never fails)
    if not requirements:
        tags = extract_tags_from_text(raw_text)
        requirements.append(
            ExtractedRequirement(
                id="req_01",
                skill_name="Demonstrated Engineering Capability",
                category="core_required",
                description=raw_text[:200].strip() or "General software engineering and problem-solving capability.",
                provenance=provenance,
                tags=tags,
                section_label="General Requirements",
                is_included=True,
                is_candidate_edited=False,
            )
        )

    return title, company, requirements
