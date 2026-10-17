import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  FileCode,
  Sparkles,
  Info,
  ArrowRight,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import type { AssessmentStatus } from '../types';
import { api, sessionStore } from '../api/client';

interface GapAssessmentItem {
  id: string;
  requirementTitle: string;
  category: 'core_required' | 'preferred_differentiator';
  status: AssessmentStatus;
  summary: string;
  suggestion: string;
  evidenceItems: Array<{
    repoName: string;
    filePath: string;
    lineRange: string;
    commitSha: string;
  }>;
}

export const SkillGapAssessmentPage = () => {
  const [statusFilter, setStatusFilter] = useState<'all' | AssessmentStatus>('all');
  const portfolioId = sessionStore.getPortfolioId();
  const jobId = sessionStore.getJobId();

  const [isLoading, setIsLoading] = useState(false);
  const [jobTitle, setJobTitle] = useState('Target Job');
  const [snapshotNum, setSnapshotNum] = useState<number>(1);
  const [assessmentItems, setAssessmentItems] = useState<GapAssessmentItem[]>([]);

  useEffect(() => {
    async function loadAssessment() {
      if (!portfolioId || !jobId) {
        // Fallback default sample data if accessed directly without active session
        setAssessmentItems([
          {
            id: 'REQ-01',
            requirementTitle: 'Go or TypeScript for Distributed Backend Services',
            category: 'core_required',
            status: 'demonstrated',
            summary: 'Direct support found in TypeScript backend handlers and database connection pool.',
            suggestion: 'Evidence is solid. Add automated concurrency benchmarks to strengthen proof.',
            evidenceItems: [
              {
                repoName: 'core-ledger-service',
                filePath: 'src/services/auth-handler.ts',
                lineRange: 'L24-L88',
                commitSha: '7f2d8a4',
              },
            ],
          },
          {
            id: 'REQ-02',
            requirementTitle: 'Event-Driven Architecture & Message Queues',
            category: 'core_required',
            status: 'partially_demonstrated',
            summary: 'RabbitMQ consumer subscriber found, but publisher confirmations and retry policies are missing.',
            suggestion: 'Implement publisher acknowledgments and dead-letter queues in data-pipeline-worker.',
            evidenceItems: [
              {
                repoName: 'data-pipeline-worker',
                filePath: 'src/workers/consumer.py',
                lineRange: 'L18-L45',
                commitSha: '91f04b2',
              },
            ],
          },
          {
            id: 'REQ-03',
            requirementTitle: 'PostgreSQL Database Design & SQL Migrations',
            category: 'core_required',
            status: 'demonstrated',
            summary: 'Relational schema models and reversible transactional SQL migrations verified.',
            suggestion: 'Add compound indexes on foreign keys to further reinforce database optimization.',
            evidenceItems: [
              {
                repoName: 'core-ledger-service',
                filePath: 'prisma/schema.prisma',
                lineRange: 'L10-L72',
                commitSha: '7f2d8a4',
              },
            ],
          },
          {
            id: 'REQ-04',
            requirementTitle: 'Kubernetes Operator Development & Custom CRDs',
            category: 'preferred_differentiator',
            status: 'not_demonstrated_in_scope',
            summary: 'No Kubernetes operator controllers or CRD manifests detected in scanned repositories. Note: absence of evidence in selected repositories does not imply you lack this skill.',
            suggestion: 'Add a minimal Go operator controller in telemetry-agent to demonstrate this skill.',
            evidenceItems: [],
          },
        ]);
        return;
      }

      setIsLoading(true);
      try {
        const runRes = await api.runAssessment(portfolioId, jobId);
        sessionStore.setRunId(runRes.id);
        setJobTitle(runRes.job_title || 'Target Job');
        setSnapshotNum(runRes.snapshot_number || 1);

        const mapped: GapAssessmentItem[] = (runRes.results || []).map((r: any) => ({
          id: r.requirement_id.toUpperCase(),
          requirementTitle: r.skill_name,
          category: r.category,
          status: r.status,
          summary: r.explanation,
          suggestion: r.suggestion || 'Review implementation evidence.',
          evidenceItems: (r.evidence_items || []).map((ev: any) => ({
            repoName: ev.repository_name || 'repository',
            filePath: ev.file_path,
            lineRange: ev.line_range || 'L1-L10',
            commitSha: (ev.commit_sha || '').slice(0, 7),
          })),
        }));

        setAssessmentItems(mapped);
      } catch (err: any) {
        console.warn('Assessment execution error:', err);
      } finally {
        setIsLoading(false);
      }
    }

    loadAssessment();
  }, [portfolioId, jobId]);

  const handleReassess = async () => {
    if (!portfolioId || !jobId) return;
    setIsLoading(true);
    try {
      const runRes = await api.runAssessment(portfolioId, jobId, 'manual_rescan');
      sessionStore.setRunId(runRes.id);
      setSnapshotNum(runRes.snapshot_number || 1);
      const mapped: GapAssessmentItem[] = (runRes.results || []).map((r: any) => ({
        id: r.requirement_id.toUpperCase(),
        requirementTitle: r.skill_name,
        category: r.category,
        status: r.status,
        summary: r.explanation,
        suggestion: r.suggestion || 'Review implementation evidence.',
        evidenceItems: (r.evidence_items || []).map((ev: any) => ({
          repoName: ev.repository_name || 'repository',
          filePath: ev.file_path,
          lineRange: ev.line_range || 'L1-L10',
          commitSha: (ev.commit_sha || '').slice(0, 7),
        })),
      }));
      setAssessmentItems(mapped);
    } catch (err: any) {
      console.error('Re-assessment error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredItems = assessmentItems.filter((item) => {
    if (statusFilter === 'all') return true;
    return item.status === statusFilter;
  });

  const counts = {
    all: assessmentItems.length,
    demonstrated: assessmentItems.filter((i) => i.status === 'demonstrated').length,
    partially_demonstrated: assessmentItems.filter((i) => i.status === 'partially_demonstrated').length,
    not_demonstrated_in_scope: assessmentItems.filter((i) => i.status === 'not_demonstrated_in_scope').length,
    uncertain: assessmentItems.filter((i) => i.status === 'uncertain').length,
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Skill Gap Assessment"
        description="Comparing target job requirements to your code evidence."
        badge={`${jobTitle} · Snapshot #${snapshotNum}`}
        breadcrumbs={[
          { label: 'Job Skills', to: '/jobs/review' },
          { label: 'Skill Map', to: '/skills' },
          { label: 'Assessment' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleReassess}
              disabled={isLoading || !portfolioId || !jobId}
              className="px-3 py-1.5 rounded-lg border border-[#8CC8F0]/40 text-xs font-medium text-[#142D4E] hover:bg-[#F8FAFC] transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Reassess</span>
            </button>
            <Link
              to="/history"
              className="px-3.5 py-1.5 rounded-lg border border-[#8CC8F0]/40 text-xs font-medium text-[#142D4E] hover:bg-[#F8FAFC] transition-colors"
            >
              View History
            </Link>
            <Link
              to="/comparison"
              className="px-4 py-1.5 rounded-lg bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-xs"
            >
              <span>Compare Snapshots</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        }
      />

      {/* Core Principle Hint */}
      <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/30 flex items-start gap-2.5 text-xs text-[#44474E]">
        <Info className="w-4 h-4 text-[#3269A8] shrink-0 mt-0.5" />
        <p>
          <strong className="text-[#142D4E]">Evaluation Note:</strong> Missing evidence in scope does not mean you lack the skill. ProofPath only verifies code present in selected repositories.
        </p>
      </div>

      {isLoading && (
        <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 text-[#3269A8] animate-spin" />
          <span className="text-xs text-[#44474E]">Evaluating candidate code evidence against job requirements...</span>
        </div>
      )}

      {/* 4 Status Filter Tabs */}
      {!isLoading && (
        <div className="flex items-center gap-1.5 border-b border-[#8CC8F0]/30 pb-2 overflow-x-auto text-xs">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-[#142D4E] text-white shadow-xs'
                : 'text-[#44474E] hover:bg-[#E7F3FC]'
            }`}
          >
            All ({counts.all})
          </button>
          <button
            onClick={() => setStatusFilter('demonstrated')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap cursor-pointer ${
              statusFilter === 'demonstrated'
                ? 'bg-[#047857] text-white shadow-xs'
                : 'text-[#047857] hover:bg-[#ECFDF5]'
            }`}
          >
            Demonstrated ({counts.demonstrated})
          </button>
          <button
            onClick={() => setStatusFilter('partially_demonstrated')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap cursor-pointer ${
              statusFilter === 'partially_demonstrated'
                ? 'bg-[#B45309] text-white shadow-xs'
                : 'text-[#B45309] hover:bg-[#FFFBEB]'
            }`}
          >
            Partially ({counts.partially_demonstrated})
          </button>
          <button
            onClick={() => setStatusFilter('not_demonstrated_in_scope')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap cursor-pointer ${
              statusFilter === 'not_demonstrated_in_scope'
                ? 'bg-[#64748B] text-white shadow-xs'
                : 'text-[#64748B] hover:bg-[#F1F5F9]'
            }`}
          >
            Not in Scope ({counts.not_demonstrated_in_scope})
          </button>
          <button
            onClick={() => setStatusFilter('uncertain')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap cursor-pointer ${
              statusFilter === 'uncertain'
                ? 'bg-[#7C3AED] text-white shadow-xs'
                : 'text-[#7C3AED] hover:bg-[#F5F3FF]'
            }`}
          >
            Uncertain ({counts.uncertain})
          </button>
        </div>
      )}

      {/* Assessment Cards List */}
      {!isLoading && (
        <div className="flex flex-col gap-3">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="bg-white border border-[#8CC8F0]/40 rounded-xl p-4 sm:p-5 shadow-xs flex flex-col gap-3"
            >
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-[#74777F]">{item.id}</span>
                  <h3 className="text-sm sm:text-base font-semibold text-[#142D4E]">
                    {item.requirementTitle}
                  </h3>
                </div>
                <StatusBadge status={item.status} size="sm" />
              </div>

              {/* Summary */}
              <p className="text-xs sm:text-sm text-[#44474E] leading-relaxed">
                {item.summary}
              </p>

              {/* Evidence items */}
              {item.evidenceItems.length > 0 && (
                <div className="flex flex-col gap-1.5 pt-2 border-t border-[#8CC8F0]/20">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-[#74777F] font-semibold">
                    Inspected Code Evidence
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {item.evidenceItems.map((ev, idx) => (
                      <Link
                        key={idx}
                        to={`/evidence?file=${encodeURIComponent(ev.filePath)}&repo=${encodeURIComponent(ev.repoName)}&lines=${encodeURIComponent(ev.lineRange)}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#E7F3FC] border border-[#8CC8F0]/40 text-xs font-mono text-[#27609E] hover:bg-[#D7EAF8] transition-colors"
                      >
                        <FileCode className="w-3.5 h-3.5 text-[#3269A8]" />
                        <span>{ev.repoName}: {ev.filePath}</span>
                        <span className="text-[#3269A8] font-semibold">{ev.lineRange}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* Suggestion / Next Action */}
              <div className="p-2.5 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/30 flex items-start gap-2 text-xs text-[#44474E]">
                <Sparkles className="w-4 h-4 text-[#3269A8] shrink-0 mt-0.5" />
                <p>
                  <strong className="text-[#142D4E]">Next Action:</strong> {item.suggestion}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
