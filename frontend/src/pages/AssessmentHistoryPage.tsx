import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  Clock,
  GitCommit,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { api, sessionStore } from '../api/client';

interface HistorySnapshot {
  id: string;
  snapshotNumber: number;
  label: string;
  timestamp: string;
  commitSha: string;
  repository: string;
  jobTitle?: string;
  demonstratedCount: number;
  partialCount: number;
  gapCount: number;
  totalRequirements: number;
}

export const AssessmentHistoryPage = () => {
  const portfolioId = sessionStore.getPortfolioId();
  const [isLoading, setIsLoading] = useState(false);
  const [snapshots, setSnapshots] = useState<HistorySnapshot[]>([]);

  useEffect(() => {
    async function loadHistory() {
      if (!portfolioId) {
        // Fallback demo state
        setSnapshots([
          {
            id: 'snap-03',
            snapshotNumber: 3,
            label: 'Snapshot #3 (Latest)',
            timestamp: '19:24:18 UTC',
            commitSha: '89a1ef4',
            repository: 'core-ledger-service',
            demonstratedCount: 3,
            partialCount: 1,
            gapCount: 1,
            totalRequirements: 5,
          },
          {
            id: 'snap-02',
            snapshotNumber: 2,
            label: 'Snapshot #2',
            timestamp: '19:10:02 UTC',
            commitSha: '7f2d8a4',
            repository: 'core-ledger-service',
            demonstratedCount: 2,
            partialCount: 2,
            gapCount: 1,
            totalRequirements: 5,
          },
          {
            id: 'snap-01',
            snapshotNumber: 1,
            label: 'Snapshot #1 (Initial)',
            timestamp: '19:04:30 UTC',
            commitSha: '01ab34f',
            repository: 'core-ledger-service',
            demonstratedCount: 1,
            partialCount: 3,
            gapCount: 1,
            totalRequirements: 5,
          },
        ]);
        return;
      }

      setIsLoading(true);
      try {
        const res = await api.listAssessments(portfolioId);
        const mapped: HistorySnapshot[] = res.runs.map((r, idx) => {
          const firstRepo = Object.keys(r.commit_references || {})[0] || 'repository';
          const firstSha = (r.commit_references || {})[firstRepo] || 'latest';
          const isLatest = idx === 0;

          return {
            id: r.id,
            snapshotNumber: r.snapshot_number,
            label: `Snapshot #${r.snapshot_number}${isLatest ? ' (Latest)' : ''}`,
            timestamp: new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            commitSha: firstSha.slice(0, 7),
            repository: firstRepo,
            jobTitle: r.job_title,
            demonstratedCount: r.status_summary.demonstrated_count,
            partialCount: r.status_summary.partially_demonstrated_count,
            gapCount: r.status_summary.not_demonstrated_in_scope_count,
            totalRequirements: r.status_summary.total_requirements,
          };
        });
        setSnapshots(mapped);
      } catch (err: any) {
        console.warn('History ledger load error:', err);
      } finally {
        setIsLoading(false);
      }
    }

    loadHistory();
  }, [portfolioId]);

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Assessment History"
        description="Track how your skill evidence changes over time."
        badge={portfolioId ? "Immutable Ledger" : "Sample Demo"}
        breadcrumbs={[
          { label: 'Assessment', to: '/assessment' },
          { label: 'History' },
        ]}
        actions={
          <Link
            to="/comparison"
            className="px-4 py-1.5 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs"
          >
            <span>Compare Snapshots</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {isLoading && (
        <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 text-[#3269A8] animate-spin" />
          <span className="text-xs text-[#44474E]">Loading assessment snapshot ledger...</span>
        </div>
      )}

      {/* Snapshot Progression Timeline */}
      {!isLoading && (
        <div className="flex flex-col gap-3">
          {snapshots.length === 0 && (
            <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl text-center text-xs text-[#44474E]">
              No assessment snapshots recorded yet. Run an assessment to generate your first immutable snapshot.
            </div>
          )}

          {snapshots.map((snap, idx) => (
            <div
              key={snap.id}
              className={`bg-white border rounded-xl p-4 sm:p-5 shadow-xs flex flex-col gap-3 transition-all ${
                idx === 0
                  ? 'border-[#3269A8]'
                  : 'border-[#8CC8F0]/40'
              }`}
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-2 border-b border-[#8CC8F0]/20">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[#142D4E] text-white">
                    {snap.label}
                  </span>
                  <span className="font-mono text-xs text-[#3269A8] flex items-center gap-1">
                    <GitCommit className="w-3.5 h-3.5" />
                    {snap.commitSha}
                  </span>
                  {snap.jobTitle && (
                    <span className="text-xs text-[#74777F] hidden sm:inline">
                      · {snap.jobTitle}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1 text-xs text-[#74777F] font-mono">
                  <Clock className="w-3.5 h-3.5 text-[#3269A8]" />
                  <span>{snap.timestamp}</span>
                </div>
              </div>

              {/* Status Breakdown Pills */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="p-2 rounded bg-[#ECFDF5] border border-[#A7F3D0] text-[#065F46]">
                  <span className="block text-[10px] text-[#047857]">DEMONSTRATED</span>
                  <span className="font-bold text-sm">{snap.demonstratedCount}</span>
                </div>
                <div className="p-2 rounded bg-[#FFFBEB] border border-[#FDE68A] text-[#92400E]">
                  <span className="block text-[10px] text-[#B45309]">PARTIAL</span>
                  <span className="font-bold text-sm">{snap.partialCount}</span>
                </div>
                <div className="p-2 rounded bg-[#F1F5F9] border border-[#CBD5E1] text-[#334155]">
                  <span className="block text-[10px] text-[#64748B]">NOT IN SCOPE</span>
                  <span className="font-bold text-sm">{snap.gapCount}</span>
                </div>
                <div className="p-2 rounded bg-[#E7F3FC] border border-[#8CC8F0]/40 text-[#142D4E]">
                  <span className="block text-[10px] text-[#27609E]">TOTAL SKILLS</span>
                  <span className="font-bold text-sm">{snap.totalRequirements}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
