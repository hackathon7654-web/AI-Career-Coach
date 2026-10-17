import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { api, sessionStore } from '../api/client';

interface TransitionItem {
  requirementId: string;
  skillName: string;
  category: string;
  baseStatus?: string;
  targetStatus: string;
  statusChanged: boolean;
  evidenceDeltaCount: number;
  explanation: string;
}

export const EvidenceComparisonPage = () => {
  const portfolioId = sessionStore.getPortfolioId();
  const [isLoading, setIsLoading] = useState(false);
  const [baseSnapNum, setBaseSnapNum] = useState<number>(1);
  const [targetSnapNum, setTargetSnapNum] = useState<number>(2);
  const [summaryDelta, setSummaryDelta] = useState<Record<string, number>>({});
  const [transitions, setTransitions] = useState<TransitionItem[]>([]);

  useEffect(() => {
    async function loadComparison() {
      if (!portfolioId) {
        // Fallback default sample data
        setTransitions([
          {
            requirementId: 'REQ-01',
            skillName: 'Go or TypeScript for Distributed Backend Services',
            category: 'core_required',
            baseStatus: 'partially_demonstrated',
            targetStatus: 'demonstrated',
            statusChanged: true,
            evidenceDeltaCount: 2,
            explanation: 'Transitioned from partially_demonstrated to demonstrated (+2 citations).',
          },
          {
            requirementId: 'REQ-02',
            skillName: 'Event-Driven Architecture & Message Queues',
            category: 'core_required',
            baseStatus: 'not_demonstrated_in_scope',
            targetStatus: 'partially_demonstrated',
            statusChanged: true,
            evidenceDeltaCount: 1,
            explanation: 'Transitioned from not_demonstrated_in_scope to partially_demonstrated (+1 citation).',
          },
          {
            requirementId: 'REQ-03',
            skillName: 'PostgreSQL Database Design & SQL Migrations',
            category: 'core_required',
            baseStatus: 'demonstrated',
            targetStatus: 'demonstrated',
            statusChanged: false,
            evidenceDeltaCount: 0,
            explanation: 'Status unchanged: demonstrated.',
          },
        ]);
        setSummaryDelta({ demonstrated_delta: 1, evidence_delta: 3 });
        return;
      }

      setIsLoading(true);
      try {
        const historyRes = await api.listAssessments(portfolioId);
        if (historyRes.runs.length >= 2) {
          const targetRun = historyRes.runs[0];
          const baseRun = historyRes.runs[1];
          setBaseSnapNum(baseRun.snapshot_number);
          setTargetSnapNum(targetRun.snapshot_number);

          const compRes = await api.compareAssessments(portfolioId, baseRun.id, targetRun.id);
          setSummaryDelta(compRes.summary_delta || {});
          setTransitions(
            compRes.transitions.map((t) => ({
              requirementId: t.requirement_id.toUpperCase(),
              skillName: t.skill_name,
              category: t.category,
              baseStatus: t.base_status,
              targetStatus: t.target_status,
              statusChanged: t.status_changed,
              evidenceDeltaCount: t.evidence_delta_count,
              explanation: t.explanation,
            }))
          );
        }
      } catch (err: any) {
        console.warn('Snapshot comparison error:', err);
      } finally {
        setIsLoading(false);
      }
    }

    loadComparison();
  }, [portfolioId]);

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Compare Evidence"
        description="Track evidence distribution and status deltas across snapshots."
        badge={portfolioId ? `Snapshot #${baseSnapNum} → #${targetSnapNum}` : "Sample Matrix (Demo)"}
        breadcrumbs={[
          { label: 'Assessment', to: '/assessment' },
          { label: 'History', to: '/history' },
          { label: 'Compare Evidence' },
        ]}
        actions={
          <Link
            to="/settings"
            className="px-4 py-1.5 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs"
          >
            <span>Settings</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {/* Delta Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 bg-white border border-[#8CC8F0]/40 rounded-xl shadow-xs font-mono">
          <span className="text-[11px] text-[#74777F] uppercase font-semibold block">Newly Demonstrated</span>
          <span className="text-xl font-bold text-[#047857] mt-0.5 block">
            {summaryDelta.demonstrated_delta !== undefined && summaryDelta.demonstrated_delta >= 0 ? `+${summaryDelta.demonstrated_delta}` : summaryDelta.demonstrated_delta || '0'}
          </span>
        </div>
        <div className="p-3.5 bg-white border border-[#8CC8F0]/40 rounded-xl shadow-xs font-mono">
          <span className="text-[11px] text-[#74777F] uppercase font-semibold block">Evidence Added</span>
          <span className="text-xl font-bold text-[#3269A8] mt-0.5 block">
            {summaryDelta.evidence_delta !== undefined && summaryDelta.evidence_delta >= 0 ? `+${summaryDelta.evidence_delta}` : summaryDelta.evidence_delta || '0'}
          </span>
        </div>
        <div className="p-3.5 bg-white border border-[#8CC8F0]/40 rounded-xl shadow-xs font-mono">
          <span className="text-[11px] text-[#74777F] uppercase font-semibold block">Base Snapshot</span>
          <span className="text-base font-bold text-[#142D4E] mt-1 block">#{baseSnapNum}</span>
        </div>
        <div className="p-3.5 bg-white border border-[#8CC8F0]/40 rounded-xl shadow-xs font-mono">
          <span className="text-[11px] text-[#74777F] uppercase font-semibold block">Target Snapshot</span>
          <span className="text-base font-bold text-[#3269A8] mt-1 block">#{targetSnapNum} (Latest)</span>
        </div>
      </div>

      {isLoading && (
        <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 text-[#3269A8] animate-spin" />
          <span className="text-xs text-[#44474E]">Computing delta transitions between snapshots...</span>
        </div>
      )}

      {/* Comparison Delta Table */}
      {!isLoading && (
        <div className="bg-white border border-[#8CC8F0]/40 rounded-xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#F8FAFC] border-b border-[#8CC8F0]/30 font-mono text-[11px] text-[#142D4E]">
                  <th className="p-3.5 font-semibold min-w-[220px]">Skill Requirement</th>
                  <th className="p-3.5 font-semibold min-w-[140px] border-l border-[#8CC8F0]/20">
                    Base Status (#{baseSnapNum})
                  </th>
                  <th className="p-3.5 font-semibold min-w-[140px] border-l border-[#8CC8F0]/20">
                    Target Status (#{targetSnapNum})
                  </th>
                  <th className="p-3.5 font-semibold min-w-[240px] border-l border-[#8CC8F0]/20">
                    Delta Rationale
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#8CC8F0]/20">
                {transitions.map((row) => (
                  <tr key={row.requirementId} className="hover:bg-[#F8FAFC]/60 transition-colors">
                    <td className="p-3.5 align-middle">
                      <div className="flex flex-col">
                        <span className="font-medium text-[#142D4E]">
                          {row.skillName}
                        </span>
                        <span className="font-mono text-[10px] text-[#74777F] uppercase mt-0.5">
                          {row.requirementId} · {row.category}
                        </span>
                      </div>
                    </td>

                    <td className="p-3.5 align-middle border-l border-[#8CC8F0]/20 font-mono text-xs">
                      <span className="text-[#64748B]">{row.baseStatus || 'unassessed'}</span>
                    </td>

                    <td className="p-3.5 align-middle border-l border-[#8CC8F0]/20 font-mono text-xs">
                      <span className={`font-semibold ${
                        row.targetStatus === 'demonstrated' ? 'text-[#047857]' :
                        row.targetStatus === 'partially_demonstrated' ? 'text-[#B45309]' : 'text-[#64748B]'
                      }`}>
                        {row.targetStatus}
                      </span>
                    </td>

                    <td className="p-3.5 align-middle border-l border-[#8CC8F0]/20 text-xs text-[#44474E]">
                      <div className="flex items-center gap-1.5">
                        {row.statusChanged && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#ECFDF5] text-[#065F46] font-semibold shrink-0">
                            CHANGED
                          </span>
                        )}
                        <span>{row.explanation}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
