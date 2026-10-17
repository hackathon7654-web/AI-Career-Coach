"""
ProofPath AI — Ground-Truth Evidence Extraction Engine
Implements deterministic, AST-aware, and syntax-based code analysis:
- File eligibility allowlists and strict security denylists (no .env, no keys, no binaries, no vendor dirs)
- Directory traversal & path normalization protection
- Secret detection and automatic redaction ([REDACTED_SECRET])
- Real 1-indexed file line numbers (line_start, line_end, line_range)
- Python AST parsing using standard library `ast`
- JavaScript / TypeScript / React / Node.js pattern extraction
- Dependency manifest parsing (package.json, requirements.txt, pyproject.toml, Dockerfile)
- CI/CD workflow parsing (.github/workflows)
- Strict evidence deduplication and volume bounds
"""
import ast
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("proofpath_ai.evidence")

# Maximum characters in an extracted snippet
MAX_SNIPPET_LENGTH = 500
# Maximum evidence items per repository
MAX_EVIDENCE_PER_REPO = 50

# Denied directory prefixes
DENIED_DIRS = (
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
    "out/",
    "vendor/",
    "target/",
    "venv/",
    ".venv/",
    "__pycache__/",
    ".idea/",
    ".vscode/",
    ".next/",
    ".nuxt/",
    "coverage/",
    ".pytest_cache/",
)

# Denied file extensions (Security & Binaries)
DENIED_EXTENSIONS = (
    # Secrets & Cryptographic material
    ".env", ".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der", ".kdbx",
    # Binaries & Archives
    ".exe", ".dll", ".so", ".dylib", ".bin", ".zip", ".tar", ".gz", ".7z", ".rar", ".iso", ".dmg",
    # Media & Assets
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".mp4", ".mp3", ".wav", ".ttf", ".woff", ".woff2", ".eot",
    # Minified / Compiled
    ".min.js", ".min.css", ".map", ".pyc", ".class",
    # Lockfiles (High noise)
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "cargo.lock",
)

# Eligible code & manifest extensions
ELIGIBLE_EXTENSIONS = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sql",
    ".json", ".toml", ".txt", ".yml", ".yaml", "dockerfile", "makefile",
)

# Secret detection patterns for automatic redaction
SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api_key|apikey|secret|token|password|auth|passwd)\s*[:=]\s*['\"][A-Za-z0-9_-]{16,}['\"]"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key ID
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"),  # GitHub Personal Access Token
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]


def redact_secrets(text: str) -> str:
    """
    Redacts discovered secret and credential patterns from code snippets.
    """
    if not text:
        return text
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def is_file_eligible(file_path: str, file_size_bytes: int, max_file_size_bytes: int = 512000) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether a file is eligible for scanning based on size, directory, and extension.
    Enforces path traversal protection.
    """
    normalized = file_path.replace("\\", "/").strip()

    # Path traversal protection
    if ".." in normalized or normalized.startswith("/") or "\0" in normalized:
        return False, "Path traversal or malformed filename rejected."

    # Size check
    if file_size_bytes > max_file_size_bytes:
        return False, f"File size ({file_size_bytes}B) exceeds safety limit ({max_file_size_bytes}B)."

    # Directory exclusion check
    lower_path = normalized.lower()
    for denied_dir in DENIED_DIRS:
        if lower_path.startswith(denied_dir) or f"/{denied_dir}" in lower_path:
            return False, f"Excluded vendor or build directory: {denied_dir}"

    # File extension / name check
    basename = os.path.basename(lower_path)

    # Check denied extensions and sensitive patterns (e.g. .env variants)
    if ".env" in basename:
        return False, "Excluded sensitive or binary file type: .env"

    for denied_ext in DENIED_EXTENSIONS:
        if basename.endswith(denied_ext) or basename == denied_ext.lstrip("."):
            return False, f"Excluded sensitive or binary file type: {denied_ext}"

    # Check eligible extensions
    is_eligible_ext = any(basename.endswith(ext) or basename == ext for ext in ELIGIBLE_EXTENSIONS)
    if not is_eligible_ext:
        return False, "Unsupported file format."

    return True, None


class EvidenceExtractor:
    """
    Analyzes code files to extract concrete, grounded skill evidence.
    """

    @classmethod
    def extract_evidence(
        cls,
        file_path: str,
        content: str,
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """
        Main extraction entry point. Dispatches by file extension.
        """
        normalized_path = file_path.replace("\\", "/")
        lower_path = normalized_path.lower()
        evidence_list: List[Dict[str, Any]] = []

        if lower_path.endswith(".py"):
            evidence_list.extend(cls._extract_python_evidence(normalized_path, content, commit_sha))
        elif lower_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            evidence_list.extend(cls._extract_javascript_evidence(normalized_path, content, commit_sha))
        elif lower_path.endswith((".json", ".txt", ".toml")) or "dockerfile" in lower_path:
            evidence_list.extend(cls._extract_manifest_evidence(normalized_path, content, commit_sha))
        elif ".github/workflows" in lower_path and lower_path.endswith((".yml", ".yaml")):
            evidence_list.extend(cls._extract_workflow_evidence(normalized_path, content, commit_sha))
        elif lower_path.endswith(".sql"):
            evidence_list.extend(cls._extract_sql_evidence(normalized_path, content, commit_sha))

        # Deduplicate evidence items
        seen_keys = set()
        deduped = []
        for item in evidence_list:
            key = (item["canonical_skill"], item["file_path"], item["line_start"])
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(item)

        return deduped[:MAX_EVIDENCE_PER_REPO]

    @classmethod
    def _extract_python_evidence(
        cls,
        file_path: str,
        content: str,
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """
        Parses Python files using standard library `ast` for ground-truth node citations.
        """
        evidence: List[Dict[str, Any]] = []
        lines = content.splitlines()

        try:
            tree = ast.parse(content, filename=file_path)
        except Exception:
            # Fallback to line-by-line inspection if AST fails (e.g. syntax dialect mismatch)
            return cls._extract_python_fallback(file_path, lines, commit_sha)

        for node in ast.walk(tree):
            # 1. Imports -> Framework & Library detection
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_names = []
                if isinstance(node, ast.Import):
                    module_names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module_names = [node.module.split(".")[0]]

                for mod in module_names:
                    skill_map = {
                        "fastapi": ("FastAPI", "High-performance Python API framework"),
                        "pydantic": ("Pydantic", "Data validation and settings management"),
                        "sqlalchemy": ("SQLAlchemy", "Python SQL toolkit and Object Relational Mapper"),
                        "pytest": ("Pytest", "Python automated testing framework"),
                        "torch": ("PyTorch", "Deep learning and neural network framework"),
                        "sklearn": ("Scikit-Learn", "Machine learning algorithms in Python"),
                        "pandas": ("Pandas", "Data analysis and tabular data manipulation"),
                        "numpy": ("NumPy", "Scientific computing and array mathematics"),
                        "asyncio": ("Asynchronous Programming", "Concurrency and async/await event loops"),
                        "django": ("Django", "Python full-stack web framework"),
                        "flask": ("Flask", "Python WSGI micro-framework"),
                        "alembic": ("Alembic", "Database schema migration tool"),
                    }
                    if mod.lower() in skill_map:
                        skill, desc = skill_map[mod.lower()]
                        line_start = node.lineno
                        line_end = getattr(node, "end_lineno", line_start)
                        snippet = cls._get_snippet(lines, line_start, line_end)
                        evidence.append({
                            "canonical_skill": skill,
                            "file_path": file_path,
                            "line_start": line_start,
                            "line_end": line_end,
                            "line_range": f"L{line_start}-L{line_end}" if line_start != line_end else f"L{line_start}",
                            "commit_sha": commit_sha,
                            "explanation": f"Discovered verified import of `{mod}`: {desc}.",
                            "evidence_type": "ast_node",
                            "ast_node_type": type(node).__name__,
                            "snippet": redact_secrets(snippet),
                            "limitations": None,
                        })

            # 2. Class Definitions -> Object-Oriented Architecture & Inheritance
            elif isinstance(node, ast.ClassDef):
                line_start = node.lineno
                line_end = min(getattr(node, "end_lineno", line_start), line_start + 5)
                base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]

                skill = "Python Class Architecture"
                expl = f"Defined class `{node.name}`."
                if any("BaseModel" in b for b in base_names):
                    skill = "Pydantic Modeling"
                    expl = f"Declared data validation model `{node.name}` inheriting from Pydantic BaseModel."
                elif any("TestCase" in b for b in base_names):
                    skill = "Unit Testing"
                    expl = f"Declared test suite class `{node.name}` inheriting from TestCase."

                snippet = cls._get_snippet(lines, line_start, line_end)
                evidence.append({
                    "canonical_skill": skill,
                    "file_path": file_path,
                    "line_start": line_start,
                    "line_end": line_end,
                    "line_range": f"L{line_start}-L{line_end}" if line_start != line_end else f"L{line_start}",
                    "commit_sha": commit_sha,
                    "explanation": expl,
                    "evidence_type": "ast_node",
                    "ast_node_type": "ClassDef",
                    "snippet": redact_secrets(snippet),
                    "limitations": None,
                })

            # 3. Async Function Definitions -> Asynchronous I/O
            elif isinstance(node, ast.AsyncFunctionDef):
                line_start = node.lineno
                line_end = min(getattr(node, "end_lineno", line_start), line_start + 4)
                snippet = cls._get_snippet(lines, line_start, line_end)
                evidence.append({
                    "canonical_skill": "Asynchronous Programming",
                    "file_path": file_path,
                    "line_start": line_start,
                    "line_end": line_end,
                    "line_range": f"L{line_start}-L{line_end}" if line_start != line_end else f"L{line_start}",
                    "commit_sha": commit_sha,
                    "explanation": f"Implemented coroutine function `async def {node.name}`.",
                    "evidence_type": "ast_node",
                    "ast_node_type": "AsyncFunctionDef",
                    "snippet": redact_secrets(snippet),
                    "limitations": None,
                })

        return evidence

    @classmethod
    def _extract_python_fallback(
        cls,
        file_path: str,
        lines: List[str],
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """Fallback line-by-line inspection when AST fails."""
        evidence: List[Dict[str, Any]] = []
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                for kw, skill in [("fastapi", "FastAPI"), ("pydantic", "Pydantic"), ("pytest", "Pytest")]:
                    if kw in stripped:
                        evidence.append({
                            "canonical_skill": skill,
                            "file_path": file_path,
                            "line_start": idx,
                            "line_end": idx,
                            "line_range": f"L{idx}",
                            "commit_sha": commit_sha,
                            "explanation": f"Discovered verified import citation for {skill}.",
                            "evidence_type": "file_match",
                            "ast_node_type": "ImportStatement",
                            "snippet": redact_secrets(stripped[:200]),
                            "limitations": "Extracted via line inspection fallback.",
                        })
        return evidence

    @classmethod
    def _extract_javascript_evidence(
        cls,
        file_path: str,
        content: str,
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """
        Deterministic syntax-aware extraction for JS/TS/React.
        """
        evidence: List[Dict[str, Any]] = []
        lines = content.splitlines()

        # TypeScript detection
        if file_path.lower().endswith((".ts", ".tsx")):
            for idx, line in enumerate(lines[:30], start=1):
                if re.search(r"\binterface\s+[A-Z]\w*|\btype\s+[A-Z]\w*\s*=", line):
                    snippet = cls._get_snippet(lines, idx, min(idx + 3, len(lines)))
                    evidence.append({
                        "canonical_skill": "TypeScript",
                        "file_path": file_path,
                        "line_start": idx,
                        "line_end": min(idx + 3, len(lines)),
                        "line_range": f"L{idx}-L{min(idx + 3, len(lines))}",
                        "commit_sha": commit_sha,
                        "explanation": "Declared static TypeScript type / interface definition.",
                        "evidence_type": "ast_node",
                        "ast_node_type": "TypeDeclaration",
                        "snippet": redact_secrets(snippet),
                        "limitations": None,
                    })
                    break

        for idx, line in enumerate(lines, start=1):
            # React Component
            if re.search(r"export\s+(?:default\s+)?(?:const|function)\s+[A-Z]\w*", line):
                snippet = cls._get_snippet(lines, idx, min(idx + 4, len(lines)))
                evidence.append({
                    "canonical_skill": "React",
                    "file_path": file_path,
                    "line_start": idx,
                    "line_end": min(idx + 4, len(lines)),
                    "line_range": f"L{idx}-L{min(idx + 4, len(lines))}",
                    "commit_sha": commit_sha,
                    "explanation": "Declared exported React functional UI component.",
                    "evidence_type": "ast_node",
                    "ast_node_type": "ComponentDeclaration",
                    "snippet": redact_secrets(snippet),
                    "limitations": None,
                })

            # React Hooks
            elif re.search(r"\b(useState|useEffect|useMemo|useCallback|useContext)\s*\(", line):
                matched_hook = re.search(r"\b(useState|useEffect|useMemo|useCallback|useContext)\b", line).group(1)
                snippet = cls._get_snippet(lines, idx, idx)
                evidence.append({
                    "canonical_skill": "React Hooks",
                    "file_path": file_path,
                    "line_start": idx,
                    "line_end": idx,
                    "line_range": f"L{idx}",
                    "commit_sha": commit_sha,
                    "explanation": f"Utilized React state/lifecycle hook `{matched_hook}`.",
                    "evidence_type": "ast_node",
                    "ast_node_type": "HookInvocation",
                    "snippet": redact_secrets(snippet),
                    "limitations": None,
                })

            # Testing (Jest / Vitest)
            elif re.search(r"^\s*(?:describe|it|test)\s*\(\s*['\"]", line):
                snippet = cls._get_snippet(lines, idx, min(idx + 3, len(lines)))
                evidence.append({
                    "canonical_skill": "Automated Testing",
                    "file_path": file_path,
                    "line_start": idx,
                    "line_end": min(idx + 3, len(lines)),
                    "line_range": f"L{idx}-L{min(idx + 3, len(lines))}",
                    "commit_sha": commit_sha,
                    "explanation": "Implemented automated unit / integration test suite specification.",
                    "evidence_type": "ast_node",
                    "ast_node_type": "TestDeclaration",
                    "snippet": redact_secrets(snippet),
                    "limitations": None,
                })

        return evidence

    @classmethod
    def _extract_manifest_evidence(
        cls,
        file_path: str,
        content: str,
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """
        Parses project manifests and package configuration files.
        """
        evidence: List[Dict[str, Any]] = []
        lower_path = file_path.lower()
        lines = content.splitlines()

        # package.json
        if lower_path.endswith("package.json"):
            try:
                data = json.loads(content)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for dep_name in deps:
                    # Find exact line in text
                    target_line = 1
                    for idx, line in enumerate(lines, start=1):
                        if f'"{dep_name}"' in line:
                            target_line = idx
                            break
                    evidence.append({
                        "canonical_skill": dep_name.capitalize(),
                        "file_path": file_path,
                        "line_start": target_line,
                        "line_end": target_line,
                        "line_range": f"L{target_line}",
                        "commit_sha": commit_sha,
                        "explanation": f"Project manifest declares dependency on package `{dep_name}`.",
                        "evidence_type": "manifest",
                        "ast_node_type": "DependencyDeclaration",
                        "snippet": redact_secrets(lines[target_line - 1].strip() if target_line <= len(lines) else ""),
                        "limitations": None,
                    })
            except Exception:
                pass

        # requirements.txt
        elif lower_path.endswith("requirements.txt"):
            for idx, line in enumerate(lines, start=1):
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    pkg = re.split(r"[=><~]", clean)[0].strip()
                    if pkg:
                        evidence.append({
                            "canonical_skill": pkg.capitalize(),
                            "file_path": file_path,
                            "line_start": idx,
                            "line_end": idx,
                            "line_range": f"L{idx}",
                            "commit_sha": commit_sha,
                            "explanation": f"Declared Python environment requirement `{pkg}`.",
                            "evidence_type": "manifest",
                            "ast_node_type": "PackageRequirement",
                            "snippet": redact_secrets(clean),
                            "limitations": None,
                        })

        # Dockerfile
        elif "dockerfile" in lower_path:
            for idx, line in enumerate(lines, start=1):
                clean = line.strip()
                if clean.startswith("FROM ") or clean.startswith("EXPOSE "):
                    evidence.append({
                        "canonical_skill": "Docker",
                        "file_path": file_path,
                        "line_start": idx,
                        "line_end": idx,
                        "line_range": f"L{idx}",
                        "commit_sha": commit_sha,
                        "explanation": "Configured container specification and base runtime environment.",
                        "evidence_type": "manifest",
                        "ast_node_type": "ContainerInstruction",
                        "snippet": redact_secrets(clean),
                        "limitations": None,
                    })

        return evidence

    @classmethod
    def _extract_workflow_evidence(
        cls,
        file_path: str,
        content: str,
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """
        Parses CI/CD GitHub Action workflows.
        """
        evidence: List[Dict[str, Any]] = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            clean = line.strip()
            if clean.startswith("uses:") or clean.startswith("runs-on:"):
                evidence.append({
                    "canonical_skill": "CI/CD & GitHub Actions",
                    "file_path": file_path,
                    "line_start": idx,
                    "line_end": idx,
                    "line_range": f"L{idx}",
                    "commit_sha": commit_sha,
                    "explanation": f"Automated workflow pipeline step: `{clean}`.",
                    "evidence_type": "workflow",
                    "ast_node_type": "WorkflowAction",
                    "snippet": redact_secrets(clean),
                    "limitations": None,
                })

    @classmethod
    def _extract_sql_evidence(
        cls,
        file_path: str,
        content: str,
        commit_sha: str,
    ) -> List[Dict[str, Any]]:
        """
        Hardened lexical scanner for SQL statements in .sql files.
        Extracts views, tables, indexes, alterations, and queries as file_match evidence.
        Robustly ignores fake SQL inside single-line comments (--), multiline comments (/* */),
        and string literals (including tagged dollar quotes $tag$...$tag$).
        """
        evidence: List[Dict[str, Any]] = []
        lines = content.splitlines()
        if not lines:
            return evidence

        sql_constructs = [
            (re.compile(r"^CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([a-zA-Z0-9_.\"]+)", re.IGNORECASE), "SQL View Definition", "SQLViewDefinition"),
            (re.compile(r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.\"]+)", re.IGNORECASE), "SQL Table Definition", "SQLTableDefinition"),
            (re.compile(r"^CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.\"]+)", re.IGNORECASE), "SQL Index Definition", "SQLIndexDefinition"),
            (re.compile(r"^ALTER\s+TABLE\s+([a-zA-Z0-9_.\"]+)", re.IGNORECASE), "SQL Table Alteration", "SQLTableAlteration"),
            (re.compile(r"^SELECT\b", re.IGNORECASE), "SQL Query Statement", "SQLQueryStatement"),
        ]

        tag_quote_pattern = re.compile(r"^\$([a-zA-Z0-9_]*)\$")

        in_block_comment = False
        in_single_quote = False
        active_dollar_tag: Optional[str] = None

        i = 0
        while i < len(lines):
            line = lines[i]
            line_num = i + 1

            clean_chars = []
            col = 0
            while col < len(line):
                if in_block_comment:
                    if line[col:col+2] == "*/":
                        in_block_comment = False
                        col += 2
                    else:
                        col += 1
                    continue

                if active_dollar_tag is not None:
                    if line[col:].startswith(active_dollar_tag):
                        col += len(active_dollar_tag)
                        active_dollar_tag = None
                    else:
                        col += 1
                    continue

                if in_single_quote:
                    if line[col] == "'" and (col == 0 or line[col-1] != "\\"):
                        if col + 1 < len(line) and line[col+1] == "'":
                            col += 2
                        else:
                            in_single_quote = False
                            col += 1
                    else:
                        col += 1
                    continue

                if line[col:col+2] == "/*":
                    in_block_comment = True
                    col += 2
                    continue

                if line[col:col+2] == "--":
                    break

                # Tagged dollar quote check e.g. $$ or $body$ or $func$
                if line[col] == "$":
                    m_tag = tag_quote_pattern.match(line[col:])
                    if m_tag:
                        active_dollar_tag = m_tag.group(0)
                        col += len(active_dollar_tag)
                        continue

                if line[col] == "'":
                    in_single_quote = True
                    col += 1
                    continue

                clean_chars.append(line[col])
                col += 1

            clean_line = "".join(clean_chars).strip()
            if not clean_line:
                i += 1
                continue

            matched = False
            for pattern, desc, node_type in sql_constructs:
                m = pattern.match(clean_line)
                if m:
                    start_line = line_num
                    end_line = start_line
                    target_name = m.group(1) if m.groups() else ""

                    j = i
                    fwd_block_comment = False
                    fwd_single_quote = False
                    fwd_dollar_tag: Optional[str] = None
                    found_semicolon = False

                    while j < len(lines) and (j - i) < 50:
                        curr = lines[j]
                        c_idx = 0
                        while c_idx < len(curr):
                            if fwd_block_comment:
                                if curr[c_idx:c_idx+2] == "*/":
                                    fwd_block_comment = False
                                    c_idx += 2
                                else:
                                    c_idx += 1
                                continue
                            if fwd_dollar_tag is not None:
                                if curr[c_idx:].startswith(fwd_dollar_tag):
                                    c_idx += len(fwd_dollar_tag)
                                    fwd_dollar_tag = None
                                else:
                                    c_idx += 1
                                continue
                            if fwd_single_quote:
                                if curr[c_idx] == "'" and (c_idx == 0 or curr[c_idx-1] != "\\"):
                                    if c_idx + 1 < len(curr) and curr[c_idx+1] == "'":
                                        c_idx += 2
                                    else:
                                        fwd_single_quote = False
                                        c_idx += 1
                                else:
                                    c_idx += 1
                                continue
                            if curr[c_idx:c_idx+2] == "/*":
                                fwd_block_comment = True
                                c_idx += 2
                                continue
                            if curr[c_idx:c_idx+2] == "--":
                                break
                            if curr[c_idx] == "$":
                                m_fwd_tag = tag_quote_pattern.match(curr[c_idx:])
                                if m_fwd_tag:
                                    fwd_dollar_tag = m_fwd_tag.group(0)
                                    c_idx += len(fwd_dollar_tag)
                                    continue
                            if curr[c_idx] == "'":
                                fwd_single_quote = True
                                c_idx += 1
                                continue
                            if curr[c_idx] == ";":
                                end_line = j + 1
                                found_semicolon = True
                                break
                            c_idx += 1

                        if found_semicolon:
                            break
                        end_line = j + 1
                        j += 1

                    snippet = redact_secrets(cls._get_snippet(lines, start_line, end_line))
                    evidence.append({
                        "canonical_skill": "SQL",
                        "file_path": file_path,
                        "line_start": start_line,
                        "line_end": end_line,
                        "line_range": f"L{start_line}-L{end_line}" if start_line != end_line else f"L{start_line}",
                        "commit_sha": commit_sha,
                        "explanation": f"Declared {desc} `{target_name}`." if target_name else f"Declared {desc}.",
                        "evidence_type": "file_match",
                        "ast_node_type": node_type,
                        "snippet": snippet,
                        "limitations": None,
                    })
                    i = end_line
                    matched = True
                    break

            if not matched:
                i += 1

        return evidence

    @staticmethod
    def _get_snippet(lines: List[str], start_1: int, end_1: int) -> str:
        """Helper to extract and truncate source line snippets."""
        s_idx = max(0, start_1 - 1)
        e_idx = min(len(lines), end_1)
        snippet_lines = lines[s_idx:e_idx]
        text = "\n".join(snippet_lines)
        if len(text) > MAX_SNIPPET_LENGTH:
            text = text[:MAX_SNIPPET_LENGTH] + "..."
        return text
