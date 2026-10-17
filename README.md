# ProofPath AI — Evidence-Grounded AI Career Coach

> **Bridging the gap between candidate resumes and verifiable engineering capability.**  
> ProofPath AI analyzes public GitHub repositories using AST parsing and static evidence extraction, matches evidence against target job descriptions, and generates honest, verifiable skill gap assessments with immutable snapshot histories.

---

## 🌐 Live Deployments

- **Frontend (Vercel):** [https://frontend-three-theta-67.vercel.app](https://frontend-three-theta-67.vercel.app)
- **Backend Architecture:** FastAPI + Uvicorn + Supabase PostgreSQL (Ready for Render deployment via `render.yaml`)

---

## 🚀 Key Features

1. **Deterministic Candidate Intake & Session Security:**
   - Cryptographically secure, high-entropy HttpOnly session tokens (`proofpath_session`).
   - Constant-time token verification, CSRF defense-in-depth, and multi-tenant portfolio isolation.

2. **Repository Discovery & Bounded Scanning:**
   - Automatic discovery of candidate GitHub repositories with elevated authenticated rate limits (5,000 req/hr).
   - Strict safety limits (max files, max payload size, 30s timeout, vendor/secret exclusions).

3. **Multi-Language Evidence Extractor:**
   - Programmatic AST analysis for Python (`ast`), TypeScript/JavaScript (`oxlint`), and SQL DDL/view definitions.
   - Exact 1-indexed line citations, deduplication, and automated secret/token redaction.

4. **Job Ingestion & Parsing:**
   - Ingests Greenhouse, Lever, and custom job postings with SSRF protection and HTML sanitization.
   - Extracts structured requirements categorized into Core and Preferred qualifications.

5. **Evidence-Based Assessment Engine:**
   - Evaluates requirements strictly against discovered code evidence (`demonstrated`, `partially_demonstrated`, `not_demonstrated_in_scope`).
   - Immutable historical snapshots with snapshot comparison matrices.

6. **Real-Time GitHub Webhooks & Activity Ledger:**
   - HMAC-SHA256 verified push event receiver with delivery idempotency.
   - Automatically executes bounded scans on code pushes and appends fresh reassessments.

---

## 📂 Project Structure

```text
.
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── api/              # Routers (health, portfolio, jobs, scans, assessments, webhooks)
│   │   ├── core/             # Configuration, session management, database clients
│   │   ├── schemas/          # Pydantic v2 data models
│   │   └── services/         # Scanner, AST/SQL extractors, assessment engine, GitHub client
│   ├── migrations/           # Hardened Supabase PostgreSQL DDL & RLS policies
│   ├── tests/                # Comprehensive pytest suite (120+ tests)
│   ├── requirements.txt      # Pinned Python dependencies
│   ├── Procfile              # Web process definition
│   └── Dockerfile            # Containerized deployment spec
├── frontend/                 # React 19 + TypeScript + Vite frontend
│   ├── src/
│   │   ├── api/              # Typed API client with loopback alignment
│   │   ├── components/       # UI components & Design System tokens
│   │   ├── pages/            # Multi-screen assessment workflow
│   │   └── types/            # TypeScript domain types
│   ├── vercel.json           # Vercel SPA routing configuration
│   └── package.json          # Frontend dependencies & scripts
├── render.yaml               # Render Blueprint for automated backend deployment
└── README.md
```

---

## 🛠️ Local Development

### 1. Backend Setup
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8001 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 3. Running Backend Tests
```bash
cd backend
pytest tests/ -v
```

---

## 🚢 Production Deployment

### Frontend (Vercel)
The frontend is pre-configured with `frontend/vercel.json` for SPA routing:
```bash
cd frontend
npx vercel --prod
```

### Backend (Render)
The repository includes `render.yaml` for Render Blueprint deployment:
1. Link this repository on [Render Dashboard](https://dashboard.render.com).
2. Create a **New Blueprint Instance** targeting `render.yaml`.
3. Provide environment secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GITHUB_TOKEN`).

---

## 🔒 Security & Privacy

- **Zero Secret Leakage:** Webhook secrets, session tokens, and database service keys are never returned in client responses or printed in server logs.
- **SSRF Defense:** Job fetcher strictly blocks loopback (`127.0.0.1`, `localhost`), link-local cloud metadata endpoints (`169.254.169.254`), and private subnets.
- **Row-Level Security:** PostgreSQL policies enforce candidate isolation at the database level.
