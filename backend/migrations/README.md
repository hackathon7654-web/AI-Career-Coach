# ProofPath AI — Database Migrations Architecture

**Target Database:** Supabase PostgreSQL (Dedicated Project: `proofpath-ai`)  
**Target Project Ref:** `rqmwizqcrtzmynhekagw` (`https://rqmwizqcrtzmynhekagw.supabase.co`)  
**Status:** **APPLIED & VERIFIED (Phase 3C Complete)**
**Note:** Existing projects `hacksync` (`zygwcpazowdsgyksooyk`) and `hacksync-staging` (`qekmmovijrsqsykrudds`) are strictly preserved and excluded.

---

## 1. Migration Inventory

| File | Purpose | Tables Affected | Execution Status |
| :--- | :--- | :--- | :--- |
| `001_initial_schema.sql` | Baseline proposal (Cascade deletes, update-only trigger) | 9 public tables | Preserved as baseline archive |
| `001_initial_schema_hardened.sql` | Hardened schema (Cascade restriction, UPDATE/DELETE/TRUNCATE trigger, session hash) | 9 public tables | **APPLIED & VERIFIED on `rqmwizqcrtzmynhekagw`** |

---

## 2. Entity-Relationship & Schema Design

```
[portfolios]
   │
   ├──< [repositories]
   │       │
   │       └──< [repository_scans]
   │               │
   │               └──< [skill_evidence]
   │
   └──< [assessment_runs] (Immutable Snapshots)
           │      ^
[jobs] ───<┘      │
   │              └── [repository_events] (Webhook deliveries)
   └──< [assessment_results]

[workspace_settings] (Singleton default configuration)
```

### Table Specifications:

1. **`portfolios`**: GitHub profile intake sessions (`id`, `github_username`, `profile_url`, `scan_status`, `timestamps`).
2. **`repositories`**: Discovered public repositories in evaluation scope (`portfolio_id`, `name`, `full_name`, `default_branch`, `last_commit_sha`, `is_eligible`, `skip_reason`, `is_selected`). Unique constraint on `(portfolio_id, full_name)`.
3. **`jobs`**: Target job requirements with provenance (`source_url`, `provenance`, `raw_text` capped at 50KB, `title`, `company`, `requirements` JSONB).
4. **`repository_scans`**: Commit-pinned scan telemetry (`repository_id`, `commit_sha`, `status`, `files_processed`, `total_files`, `skipped_summary`).
5. **`skill_evidence`**: Atomic ground-truth code citations. Uses **structured integer line numbers** (`line_start`, `line_end` with `line_end >= line_start`) plus formatted `line_range` string. Snippet text capped at 10KB.
6. **`assessment_runs`**: Immutable chronological evaluation snapshots (`portfolio_id`, `job_id`, `snapshot_number`, `trigger_type`, `commit_references`, `triggering_event_id`). Unique on `(portfolio_id, job_id, snapshot_number)`.
7. **`assessment_results`**: Requirement-level evaluation status constrained to the 4 PRD states: `demonstrated`, `partially_demonstrated`, `not_demonstrated_in_scope`, `uncertain`.
8. **`repository_events`**: Inbound GitHub push webhook deliveries. Deduplicated via unique `delivery_id` (`X-GitHub-Delivery`) with HMAC status and retry counter.
9. **`workspace_settings`**: Configurable scan limits and exclusions with a unique partial index on `is_default = true`.

---

## 3. Snapshot Immutability Guarantee

To fulfill PRD Requirement **FR-13** (*"Historical snapshots must not be overwritten. Old/new snapshots preserved and evidence delta explained"*), `001_initial_schema.sql` defines a PL/pgSQL trigger:

```sql
CREATE OR REPLACE FUNCTION public.prevent_assessment_snapshot_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Assessment snapshot records are immutable and cannot be updated or modified once created.';
END;
$$ LANGUAGE plpgsql;
```

This prevents any accidental or unauthorized `UPDATE` statements on `assessment_runs` and `assessment_results` once committed.

---

## 4. Row Level Security (RLS) & Access Privilege Matrix

| Database Role | Read (SELECT) | Write (INSERT/UPDATE/DELETE) | Access Channel | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`service_role`** | **ALLOWED** | **ALLOWED** | Server-side FastAPI backend | Uses secret `SUPABASE_SERVICE_ROLE_KEY` or direct connection; bypasses RLS. |
| **`anon`** | **DENIED** | **DENIED** | Browser client via Supabase REST | All privileges revoked on public tables to prevent unauthorized scraping or tampering. |
| **`authenticated`** | **DENIED** | **DENIED** | Browser client with user JWT | Denied by default; no multi-user auth model exists in current PRD scope. |

### Why this model is safe:
In a 3-tier architecture with FastAPI, all business logic, SSRF validation, GitHub token calls, and evidence generation are performed on the trusted server. Direct browser-to-database access via the public anon key is completely disabled by default.

---

## 5. Execution Status (Phase 3C Complete)
- Applied: `001_initial_schema_hardened.sql`
- Target: `proofpath-ai` (`rqmwizqcrtzmynhekagw`)
- Verified: All 9 public tables, 30 indexes, RLS enabled, anon/authenticated revoked, service_role granted, UPDATE/DELETE/TRUNCATE immutability triggers active.
- Next Phase: Phase 3D (Intake, GitHub API scanning & session authorization implementation).


