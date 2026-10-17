"""
ProofPath AI — SQL Evidence Extractor & Pipeline Tests
Verifies Track A requirements:
- Stateful lexical extraction of views, tables, indexes, alterations, and queries
- Evidence schema conformance: evidence_type = 'file_match', canonical_skill = 'SQL'
- Non-misrepresentation: regex/pattern matches are labeled file_match, not ast_node
- Rejection of SQL statements hidden in -- line comments and /* */ block comments
- Rejection of SQL statements inside single-quoted string literals and dollar quotes
- Secret redaction within extracted SQL code snippets
- Exact 1-indexed line start, end, and line range formatting
- Assessment engine integration against database/SQL requirements (evaluating to partially_demonstrated)
"""
import pytest
from app.services.evidence_extractor import EvidenceExtractor, redact_secrets
from app.services.assessment_engine import (
    match_evidence_to_requirement,
    evaluate_requirement,
)
from app.schemas.job import ExtractedRequirement


SAMPLE_COMMIT_SHA = "462ec7fd70861de0a9d19ca682037bfc7dc52972"


def test_sql_view_definition_extraction():
    """Verify multiline CREATE VIEW extraction with security_invoker clause."""
    sql = """-- Team Storage Summary View
CREATE OR REPLACE VIEW public.team_storage_summary
WITH (security_invoker = true) AS
SELECT
    t.id AS team_id,
    t.name AS team_name,
    COUNT(f.id) AS total_files
FROM public.teams t
LEFT JOIN public.shared_files f ON t.id = f.team_id
GROUP BY t.id, t.name;
"""
    evidence = EvidenceExtractor.extract_evidence("supabase/migrations/001_view.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev["canonical_skill"] == "SQL"
    assert ev["evidence_type"] == "file_match"
    assert ev["ast_node_type"] == "SQLViewDefinition"
    assert ev["line_start"] == 2
    assert ev["line_end"] == 10
    assert ev["line_range"] == "L2-L10"
    assert ev["commit_sha"] == SAMPLE_COMMIT_SHA
    assert "public.team_storage_summary" in ev["explanation"]
    assert "CREATE OR REPLACE VIEW" in ev["snippet"]


def test_sql_ddl_and_dml_constructs():
    """Verify table, index, alter, and select extraction with distinct line ranges."""
    sql = """CREATE TABLE public.teams (
    id uuid PRIMARY KEY,
    name text NOT NULL
);

CREATE INDEX idx_teams_name ON public.teams (name);

ALTER TABLE public.teams ADD COLUMN active boolean DEFAULT true;

SELECT id, name FROM public.teams WHERE active = true;
"""
    evidence = EvidenceExtractor.extract_evidence("schema.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(evidence) == 4

    types = [e["ast_node_type"] for e in evidence]
    assert types == ["SQLTableDefinition", "SQLIndexDefinition", "SQLTableAlteration", "SQLQueryStatement"]

    # Verify line ranges
    assert evidence[0]["line_range"] == "L1-L4"
    assert evidence[1]["line_range"] == "L6"
    assert evidence[2]["line_range"] == "L8"
    assert evidence[3]["line_range"] == "L10"


def test_fake_sql_in_comments_ignored():
    """Verify that comments containing SQL keywords do NOT produce fake evidence."""
    sql = """-- CREATE TABLE fake_users (id int, password text);
-- SELECT * FROM credentials;
/*
CREATE OR REPLACE VIEW fake_admin_view AS
SELECT * FROM secrets;
*/
-- ALTER TABLE users ADD COLUMN secret_key text;
"""
    evidence = EvidenceExtractor.extract_evidence("comments_only.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(evidence) == 0, f"Expected 0 evidence from comments, got {len(evidence)}"


def test_fake_sql_in_string_literals_ignored():
    """Verify that SQL statements inside strings/inserts do NOT produce fake evidence."""
    sql = """INSERT INTO event_logs (payload) VALUES ('CREATE TABLE secret (id int);');
INSERT INTO audit_trail (message) VALUES ('SELECT * FROM users;');
"""
    evidence = EvidenceExtractor.extract_evidence("inserts.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(evidence) == 0, f"Expected 0 evidence from strings, got {len(evidence)}"


def test_semicolon_inside_string_does_not_prematurely_truncate():
    """Verify that a semicolon inside a string literal does not split the statement."""
    sql = """SELECT
    t.id,
    '; -- this is not a terminator' AS remark,
    t.name
FROM public.teams t;
"""
    evidence = EvidenceExtractor.extract_evidence("query.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(evidence) == 1
    assert evidence[0]["line_range"] == "L1-L5"
    assert "public.teams" in evidence[0]["snippet"]


def test_secret_redaction_in_sql_snippets():
    """Verify that credentials and tokens embedded in SQL snippets are redacted."""
    sql = """-- Configuration script
CREATE TABLE public.api_credentials (
    id uuid PRIMARY KEY,
    api_key text DEFAULT 'api_key: "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"'
);
"""
    evidence = EvidenceExtractor.extract_evidence("creds.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(evidence) == 1
    snippet = evidence[0]["snippet"]
    assert "ghp_" not in snippet
    assert "[REDACTED_SECRET]" in snippet


def test_empty_and_malformed_sql():
    """Verify graceful handling of empty files and unterminated comments."""
    assert EvidenceExtractor.extract_evidence("empty.sql", "", SAMPLE_COMMIT_SHA) == []
    assert EvidenceExtractor.extract_evidence("whitespace.sql", "   \n\n\t  \n", SAMPLE_COMMIT_SHA) == []

    unterminated = """/* Unterminated comment block
    CREATE TABLE orphaned (id int);
    """
    assert EvidenceExtractor.extract_evidence("broken.sql", unterminated, SAMPLE_COMMIT_SHA) == []


def test_assessment_engine_sql_requirement_matching():
    """
    Verify integration with the real assessment engine pipeline.
    Confirms that SQL file_match evidence:
    1. Matches a database/SQL requirement (like Sezzle req_07).
    2. Correctly evaluates to 'partially_demonstrated' (not claiming broad database expertise).
    3. Cites exact file, line range, and commit SHA.
    """
    req_07 = ExtractedRequirement(
        id="req_07",
        skill_name="Basic understanding of databases and SQL",
        category="core_required",
        tags=["Database", "SQL"],
        provenance="extracted",
    )

    sql_content = """CREATE OR REPLACE VIEW public.team_storage_summary
WITH (security_invoker = true) AS
SELECT
    t.id AS team_id,
    t.name AS team_name,
    COUNT(f.id) AS total_files
FROM public.teams t
LEFT JOIN public.shared_files f ON t.id = f.team_id
GROUP BY t.id, t.name;
"""
    extracted_items = EvidenceExtractor.extract_evidence(
        "supabase/migrations/20261017000000_team_storage_summary.sql",
        sql_content,
        SAMPLE_COMMIT_SHA,
    )
    assert len(extracted_items) == 1

    # Simulate database persistence format
    mock_db_evidence = [
        {
            "id": "ev-sql-001",
            "repository_id": "repo-hacksync",
            "canonical_skill": extracted_items[0]["canonical_skill"],
            "file_path": extracted_items[0]["file_path"],
            "line_start": extracted_items[0]["line_start"],
            "line_end": extracted_items[0]["line_end"],
            "line_range": extracted_items[0]["line_range"],
            "commit_sha": extracted_items[0]["commit_sha"],
            "explanation": extracted_items[0]["explanation"],
            "evidence_type": extracted_items[0]["evidence_type"],
            "ast_node_type": extracted_items[0]["ast_node_type"],
            "snippet": extracted_items[0]["snippet"],
        }
    ]

    # Test matching
    matched = match_evidence_to_requirement(req_07, mock_db_evidence)
    assert len(matched) == 1, "Evidence with canonical_skill='SQL' must match req_07"

    # Test assessment evaluation
    repo_map = {"repo-hacksync": "samerrjaiswal-ctrl/hacksync"}
    result = evaluate_requirement(req_07, matched, repo_map, total_scanned_repos=1)

    # Must be partially_demonstrated to prevent overclaiming broad database expertise
    assert result.status == "partially_demonstrated"
    assert len(result.evidence_ids) == 1
    assert result.evidence_ids[0] == "ev-sql-001"
    assert result.evidence_items[0].line_range == "L1-L9"
    assert result.evidence_items[0].commit_sha == SAMPLE_COMMIT_SHA
    assert result.evidence_items[0].evidence_type == "file_match"
    # Verify refined SQL-specific explanation
    assert "Found declarative database schema / SQL definition in" in result.explanation
    assert "schema modeling and SQL construct definition" in result.explanation
    assert "Evidence grounded in declarative SQL schema" in result.limitations


def test_sql_tagged_dollar_quotes():
    """Verify PostgreSQL tagged dollar quotes like $body$...$body$ and $func$...$func$."""
    sql = """CREATE OR REPLACE FUNCTION update_metrics()
RETURNS void AS $body$
BEGIN
    -- Comment inside dollar quotes should not terminate or fake DDL
    SELECT 1 FROM public.teams;
END;
$body$ LANGUAGE plpgsql;

CREATE TABLE public.metrics (
    id serial PRIMARY KEY,
    description text DEFAULT $val$Text with ; inside tagged dollar quote$val$
);
"""
    ev = EvidenceExtractor.extract_evidence("functions.sql", sql, SAMPLE_COMMIT_SHA)
    assert len(ev) == 1
    assert ev[0]["ast_node_type"] == "SQLTableDefinition"
    assert ev[0]["line_start"] == 9
    assert ev[0]["line_end"] == 12
    assert "public.metrics" in ev[0]["explanation"]

