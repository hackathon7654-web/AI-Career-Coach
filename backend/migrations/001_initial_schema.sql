-- ==============================================================================
-- ProofPath AI — Migration 001: Initial Relational Schema & Security Policies
-- Target: Supabase PostgreSQL (Project ref: zygwcpazowdsgyksooyk)
-- Status: PREPARED FOR REVIEW ONLY — DO NOT EXECUTE REMOTELY WITHOUT APPROVAL
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 0. EXTENSIONS & PREREQUISITES
-- ------------------------------------------------------------------------------
-- Ensure pgcrypto or native gen_random_uuid() is accessible in schema extensions/public
CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA extensions;

-- ------------------------------------------------------------------------------
-- 1. PORTFOLIOS
-- Represents a candidate's GitHub portfolio intake session.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_username TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    scan_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (scan_status IN ('pending', 'scanning', 'completed', 'partial', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.portfolios IS 'GitHub portfolio intake sessions.';
CREATE INDEX IF NOT EXISTS idx_portfolios_username ON public.portfolios (github_username);
CREATE INDEX IF NOT EXISTS idx_portfolios_created_at ON public.portfolios (created_at DESC);

-- ------------------------------------------------------------------------------
-- 2. REPOSITORIES
-- Discovered public GitHub repositories belonging to a candidate portfolio.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    html_url TEXT NOT NULL,
    description TEXT,
    default_branch TEXT NOT NULL DEFAULT 'main',
    last_commit_sha TEXT,
    is_eligible BOOLEAN NOT NULL DEFAULT true,
    skip_reason TEXT,
    language TEXT,
    stars INT NOT NULL DEFAULT 0 CHECK (stars >= 0),
    is_selected BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_repositories_portfolio_fullname UNIQUE (portfolio_id, full_name)
);

COMMENT ON TABLE public.repositories IS 'Discovered GitHub repositories under evaluation scope.';
CREATE INDEX IF NOT EXISTS idx_repositories_portfolio_id ON public.repositories (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_repositories_is_selected ON public.repositories (portfolio_id, is_selected);

-- ------------------------------------------------------------------------------
-- 3. JOBS
-- Ingested target job descriptions and extracted qualification criteria.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url TEXT,
    provenance TEXT NOT NULL DEFAULT 'user_pasted'
        CHECK (provenance IN ('fetched', 'user_pasted')),
    raw_text TEXT CHECK (length(raw_text) <= 50000), -- 50KB retention limit
    title TEXT NOT NULL,
    company TEXT,
    requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieval_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    limitations TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.jobs IS 'Target job postings with structured requirements and provenance.';
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON public.jobs (created_at DESC);

-- ------------------------------------------------------------------------------
-- 4. REPOSITORY_SCANS
-- Bounded repository AST and file-tree parsing runs pinned to commit SHAs.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.repository_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES public.repositories(id) ON DELETE CASCADE,
    commit_sha TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'partial', 'failed')),
    files_processed INT NOT NULL DEFAULT 0 CHECK (files_processed >= 0),
    total_files INT NOT NULL DEFAULT 0 CHECK (total_files >= 0),
    skipped_summary VARCHAR(1000),
    duration_ms INT CHECK (duration_ms >= 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

COMMENT ON TABLE public.repository_scans IS 'Bounded code scanning telemetry pinned to commit SHAs.';
CREATE INDEX IF NOT EXISTS idx_repository_scans_repo_id ON public.repository_scans (repository_id);
CREATE INDEX IF NOT EXISTS idx_repository_scans_commit_sha ON public.repository_scans (commit_sha);

-- ------------------------------------------------------------------------------
-- 5. SKILL_EVIDENCE
-- Atomic, inspectable code evidence mapped to verified file lines and AST nodes.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.skill_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES public.repository_scans(id) ON DELETE CASCADE,
    repository_id UUID NOT NULL REFERENCES public.repositories(id) ON DELETE CASCADE,
    canonical_skill TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_start INT CHECK (line_start IS NULL OR line_start > 0),
    line_end INT CHECK (line_end IS NULL OR line_end >= line_start),
    line_range TEXT, -- Human-readable format, e.g. "L24-L58"
    commit_sha TEXT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_type TEXT DEFAULT 'ast_node'
        CHECK (evidence_type IN ('ast_node', 'file_match', 'manifest', 'workflow')),
    ast_node_type TEXT,
    snippet TEXT CHECK (snippet IS NULL OR length(snippet) <= 10000), -- 10KB cap
    limitations TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.skill_evidence IS 'Ground-truth code evidence citations tied to exact files/lines.';
CREATE INDEX IF NOT EXISTS idx_skill_evidence_scan_id ON public.skill_evidence (scan_id);
CREATE INDEX IF NOT EXISTS idx_skill_evidence_repo_id ON public.skill_evidence (repository_id);
CREATE INDEX IF NOT EXISTS idx_skill_evidence_skill ON public.skill_evidence (canonical_skill);

-- ------------------------------------------------------------------------------
-- 6. ASSESSMENT_RUNS (Immutable Snapshots)
-- Evaluation run snapshots tying portfolio code evidence to target job requirements.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.assessment_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    snapshot_number INT NOT NULL CHECK (snapshot_number > 0),
    trigger_type TEXT NOT NULL DEFAULT 'initial_scan'
        CHECK (trigger_type IN ('initial_scan', 'webhook_push', 'manual_rescan')),
    commit_references JSONB NOT NULL DEFAULT '{}'::jsonb,
    triggering_event_id UUID, -- References repository_events(id) if triggered by webhook
    status_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_assessment_runs_snapshot UNIQUE (portfolio_id, job_id, snapshot_number)
);

COMMENT ON TABLE public.assessment_runs IS 'Immutable chronological assessment snapshots.';
CREATE INDEX IF NOT EXISTS idx_assessment_runs_portfolio ON public.assessment_runs (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_assessment_runs_job ON public.assessment_runs (job_id);

-- ------------------------------------------------------------------------------
-- 7. ASSESSMENT_RESULTS
-- Requirement-level evaluation states (Demonstrated, Partial, Not in Scope, Uncertain).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.assessment_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_run_id UUID NOT NULL REFERENCES public.assessment_runs(id) ON DELETE CASCADE,
    requirement_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'core_required'
        CHECK (category IN ('core_required', 'preferred_differentiator')),
    status TEXT NOT NULL
        CHECK (status IN ('demonstrated', 'partially_demonstrated', 'not_demonstrated_in_scope', 'uncertain')),
    explanation TEXT NOT NULL,
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of skill_evidence.id references
    limitations TEXT,
    suggestion TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.assessment_results IS 'Per-requirement assessment results grounded in code evidence.';
CREATE INDEX IF NOT EXISTS idx_assessment_results_run_id ON public.assessment_results (assessment_run_id);
CREATE INDEX IF NOT EXISTS idx_assessment_results_status ON public.assessment_results (status);

-- ------------------------------------------------------------------------------
-- 8. REPOSITORY_EVENTS (GitHub Webhook Ingestion)
-- Webhook deliveries with HMAC verification, delivery idempotency, and reassessment tracking.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.repository_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id TEXT NOT NULL UNIQUE, -- GitHub X-GitHub-Delivery GUID for idempotency
    repository_name TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'push',
    commit_sha TEXT NOT NULL,
    changed_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hmac_verified BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'completed', 'duplicate', 'failed')),
    reassessment_run_id UUID REFERENCES public.assessment_runs(id) ON DELETE SET NULL,
    retry_count INT NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    error_details VARCHAR(2000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.repository_events IS 'Inbound GitHub webhook event ledger with idempotency.';
CREATE INDEX IF NOT EXISTS idx_repository_events_delivery_id ON public.repository_events (delivery_id);
CREATE INDEX IF NOT EXISTS idx_repository_events_created_at ON public.repository_events (created_at DESC);

-- Add foreign key reference from assessment_runs to repository_events safely
ALTER TABLE public.assessment_runs
    ADD CONSTRAINT fk_assessment_runs_triggering_event
    FOREIGN KEY (triggering_event_id) REFERENCES public.repository_events(id) ON DELETE SET NULL;

-- ------------------------------------------------------------------------------
-- 9. WORKSPACE_SETTINGS
-- Global / workspace operational settings (file thresholds, exclusions, automation).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workspace_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_default BOOLEAN NOT NULL DEFAULT true,
    max_file_size_mb NUMERIC(4, 2) NOT NULL DEFAULT 1.00 CHECK (max_file_size_mb > 0 AND max_file_size_mb <= 5.00),
    default_branch_scope TEXT NOT NULL DEFAULT 'default' CHECK (default_branch_scope IN ('default', 'all')),
    auto_reassess_on_push BOOLEAN NOT NULL DEFAULT true,
    excluded_patterns JSONB NOT NULL DEFAULT '["node_modules/","dist/","build/","vendor/","*.min.js","*.env*","*.pem"]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ensure only one default settings record exists while leaving room for multi-workspace extensions
CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_settings_default
    ON public.workspace_settings (is_default) WHERE is_default = true;

COMMENT ON TABLE public.workspace_settings IS 'Workspace scan boundaries and automation preferences.';

-- ------------------------------------------------------------------------------
-- 10. ASSESSMENT SNAPSHOT IMMUTABILITY ENFORCEMENT
-- Prevent accidental or unauthorized modification of historical assessment records.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.prevent_assessment_snapshot_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Assessment snapshot records are immutable and cannot be updated or modified once created.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_assessment_runs ON public.assessment_runs;
CREATE TRIGGER trg_immutable_assessment_runs
    BEFORE UPDATE ON public.assessment_runs
    FOR EACH ROW EXECUTE FUNCTION public.prevent_assessment_snapshot_modification();

DROP TRIGGER IF EXISTS trg_immutable_assessment_results ON public.assessment_results;
CREATE TRIGGER trg_immutable_assessment_results
    BEFORE UPDATE ON public.assessment_results
    FOR EACH ROW EXECUTE FUNCTION public.prevent_assessment_snapshot_modification();

-- ------------------------------------------------------------------------------
-- 11. ROW LEVEL SECURITY (RLS) & PRIVILEGE ARCHITECTURE
-- ------------------------------------------------------------------------------
-- Enable RLS across all 9 public tables
ALTER TABLE public.portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.repositories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.repository_scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skill_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessment_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessment_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.repository_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_settings ENABLE ROW LEVEL SECURITY;

-- Security Principle:
-- In a 3-tier architecture with FastAPI, all database access is mediated by the trusted backend
-- using the service_role key (which bypasses RLS) or direct postgres credentials.
--
-- Direct browser access via the Supabase public anon key is REVOKED by default.
-- This prevents any unauthorized client from directly reading, scraping, or mutating
-- candidate resumes, raw job text, evidence, or webhook deliveries.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated;

-- Grant access to service_role (used by FastAPI server-side client)
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- Documented Decision Point for Multi-tenant Extension:
-- If public read-only viewing of specific assessment snapshots is desired via anon key in the future,
-- explicit scoped policies (e.g. SELECT on public.assessment_runs WHERE is_public = true)
-- can be added after user identity / sharing requirements are formally approved.
