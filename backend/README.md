# ProofPath AI — Backend API

Backend foundation and assessment engine for **ProofPath AI** (Evidence-First AI Career Coach). Built with FastAPI, Pydantic v2, Python 3.13, and PostgreSQL on Supabase.

---

## 1. Local Setup & Activation (Windows PowerShell)

All required dependencies are pinned in `requirements.txt`:

```powershell
# Navigate to backend directory
cd C:\Users\Sameer\OneDrive\Desktop\dyhack\backend

# Run tests
python -m pytest tests/ -v

# Start development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 2. Environment Configuration (`.env`)

Configure local settings via `backend/.env` (see `backend/.env.example` for reference):

| Variable | Type | Description | Required / Optional |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | string | Application identifier | Default: `"ProofPath AI API"` |
| `APP_ENV` | string | Environment: `development` \| `production` | Default: `"development"` |
| `DEBUG` | boolean | Enables debug mode | Default: `false` |
| `FRONTEND_ORIGINS` | JSON list | Allowed CORS origins | Default: `["http://localhost:5173"]` |
| `SUPABASE_URL` | string | Dedicated Supabase project URL | Required for live database operations |
| `SUPABASE_SERVICE_ROLE_KEY` | string | Privileged server-side key | Required for live database operations |
| `GITHUB_TOKEN` | string | Optional GitHub Personal Access Token | Optional (increases rate limit from 60 to 5,000 req/hr) |
| `SESSION_COOKIE_NAME` | string | Intake session cookie name | Default: `proofpath_session` |
| `SESSION_MAX_AGE_SECONDS`| integer | Candidate session lifetime (seconds) | Default: `604800` (7 days) |
| `SESSION_COOKIE_SECURE` | boolean | HTTPS cookie attribute | Auto (`false` in dev, `true` in prod) |
| `MAX_FILES_PER_REPO` | integer | Maximum eligible files scanned per repo | Hard Ceiling: `50` |
| `MAX_FILE_SIZE_BYTES` | integer | Maximum per-file download size | Hard Ceiling: `512000` (500 KB) |
| `MAX_TOTAL_REPO_BYTES` | integer | Maximum accumulated bytes per repo | Hard Ceiling: `10485760` (10 MB) |
| `SCAN_TIMEOUT_SECONDS` | float | Execution ceiling per repository | Hard Ceiling: `30.0` seconds |

---

## 3. API Endpoints & Authentication

### A. Candidate Intake & Session Management

#### `POST /api/portfolio/intake`
Creates a candidate portfolio session, issues a 256-bit entropy session token, sets an `HttpOnly`, `SameSite=Lax`, `Path=/` session cookie, and returns the portfolio ID.

**Request:**
```json
{
  "github_username": "octocat"
}
```

**Response (`201 Created`):**
```json
{
  "portfolio_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "github_username": "octocat",
  "profile_url": "https://github.com/octocat",
  "scan_status": "pending",
  "created_at": "2026-10-16T18:00:00+00:00",
  "message": "Candidate session initialized. Cookie set."
}
```

---

### B. Repository Discovery & Selection (Phase 3D-2)

#### `GET /api/portfolio/{portfolio_id}/repositories/discover`
*Requires valid session for `portfolio_id`.*  
Discovers candidate's public repositories from GitHub with pagination bounds (max 5 pages, max 50 items/page). Automatically determines qualification (e.g. skips forks, archived repositories, and empty repositories with clear `skip_reason`), and persists them into the database.

**Query Parameters:**
- `page`: integer (1–5, default: 1)
- `per_page`: integer (1–50, default: 30)

**Response (`200 OK`):**
```json
{
  "portfolio_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "github_username": "octocat",
  "page": 1,
  "per_page": 30,
  "total_discovered": 12,
  "repositories": [
    {
      "id": "98765432-abcd-ef01-2345-6789abcdef01",
      "name": "algo-visualizer",
      "full_name": "octocat/algo-visualizer",
      "html_url": "https://github.com/octocat/algo-visualizer",
      "description": "Interactive graph algorithm animator",
      "default_branch": "main",
      "language": "TypeScript",
      "stars": 42,
      "is_eligible": true,
      "skip_reason": null,
      "is_selected": true,
      "last_commit_sha": null
    }
  ]
}
```

#### `PATCH /api/portfolio/{portfolio_id}/repositories/select`
*Requires valid session for `portfolio_id` and CSRF protection.*  
Updates candidate's selected evaluation scope. Strictly verifies portfolio ownership for every submitted repository ID (rejects cross-portfolio IDOR attempts with `403 Forbidden`). Max 10 repositories.

**Request:**
```json
{
  "repository_ids": ["98765432-abcd-ef01-2345-6789abcdef01"]
}
```

**Response (`200 OK`):**
```json
{
  "portfolio_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "selected_count": 1,
  "repositories": [...]
}
```

---

### C. Bounded Scanning & Evidence Extraction (Phase 3D-3)

#### `POST /api/portfolio/{portfolio_id}/scan`
*Requires valid session for `portfolio_id`.*  
Triggers deterministic bounded code scanning on selected repositories:
1. Resolves branch commit SHA (`git rev-parse HEAD` equivalent via GitHub API).
2. Pins all file tree and blob fetches to that exact commit SHA.
3. Filters files through strict security eligibility (excludes `.env`, `.pem`, private keys, binaries, vendor dirs).
4. Enforces hard safety budgets: max 50 files, max 500 KB/file, max 10 MB total, max 30s per repo.
5. Performs real deterministic AST extraction (Python `ast.parse` and JS/TS component analysis).
6. Redacts detected secret patterns to `[REDACTED_SECRET]`.
7. Persists ground-truth citations into `skill_evidence` and telemetry into `repository_scans`.

**Response (`200 OK`):**
```json
{
  "portfolio_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "portfolio_status": "completed",
  "total_repositories_selected": 2,
  "scans_completed": 2,
  "scans_running": 0,
  "scans_failed": 0,
  "total_evidence_count": 38,
  "scans": [
    {
      "scan_id": "550e8400-e29b-41d4-a716-446655440000",
      "repository_id": "98765432-abcd-ef01-2345-6789abcdef01",
      "repository_name": "octocat/algo-visualizer",
      "commit_sha": "7b0a10d0f74043da926f54c51320005c12345678",
      "status": "completed",
      "files_processed": 14,
      "total_files": 14,
      "skipped_summary": "Processed 14 files (384120 bytes). Skipped 4 files.",
      "duration_ms": 1420,
      "started_at": "2026-10-16T18:05:00+00:00",
      "completed_at": "2026-10-16T18:05:01.420000+00:00"
    }
  ]
}
```

#### `GET /api/portfolio/{portfolio_id}/scan/status`
*Requires valid session for `portfolio_id`.*  
Returns real-time scan progress, per-repository telemetry, and evidence counts from database.

#### `GET /api/portfolio/{portfolio_id}/evidence`
*Requires valid session for `portfolio_id`.*  
Fetches atomic, ground-truth code evidence citations with line ranges (e.g. `L12-L45`), AST node types, and sanitized explanations.

---

## 4. Security & Safety Architecture

1. **SSRF Prevention:** All external requests target strictly `https://api.github.com/`. Target host validation rejects non-approved hosts, loopback addresses (`127.0.0.1`), and cloud metadata (`169.254.169.254`). Redirects to unapproved hosts are rejected.
2. **Commit-SHA Pinning:** Every scan resolves the default branch commit SHA first. File tree and blob fetching are permanently bound to that SHA, guaranteeing immutability across rescans.
3. **Secret Redaction & Exclusion:** Sensitive files (`.env*`, `.pem`, `.key`, `.p12`, `.crt`, `.kdbx`, `id_rsa`) and vendor directories (`node_modules/`, `.git/`, `dist/`, `build/`, `vendor/`) are excluded before fetching. Source snippets undergo regex redaction of AWS keys, GitHub tokens, and JWTs.
4. **No Code Execution:** Repository contents are analyzed purely via static syntax inspection and standard library `ast.parse()`. No candidate code is ever imported, built, or executed.
5. **IDOR & Session Defense:** Routes enforce candidate session validity using constant-time `hmac.compare_digest`. Route parameter `portfolio_id` is validated against the authenticated session token. Cross-portfolio repository access is rejected with `403 Forbidden`.
6. **Rate-Limit Resilience:** GitHub rate-limit headers (`x-ratelimit-remaining`, `x-ratelimit-reset`, `retry-after`) are parsed proactively. If limits are reached, the system fails fast with a sanitized `429 Too Many Requests` error rather than retrying indefinitely.

---

## 5. Architectural Limitations & Current Boundaries

- **Single-Host Scanning:** Scans currently target public GitHub repositories via REST API. Private repositories, GitLab, and Bitbucket are excluded in this subphase.
- **In-Process Bounded Concurrency:** Scanning executes with bounded concurrency (`asyncio.Semaphore(5)`). For very large enterprise deployments, a dedicated task queue (Celery/Temporal) can be added in future scaling phases.
- **Languages Analyzed:** Deterministic ground-truth evidence extraction currently supports Python (full AST), TypeScript / JavaScript / React (syntax patterns & hooks), project manifests (package.json, requirements.txt, pyproject.toml, Dockerfile), and CI/CD workflows (.github/workflows). Other file extensions are validated for existence and language metadata.
