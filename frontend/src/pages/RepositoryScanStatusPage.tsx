import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  CheckCircle2,
  FolderGit2,
  ArrowRight,
  GitCommit,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import type { ScanStatusItem } from '../types';
import { api, sessionStore } from '../api/client';

export const RepositoryScanStatusPage = () => {
  const navigate = useNavigate();
  const portfolioId = sessionStore.getPortfolioId();

  const [isLoading, setIsLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [portfolioStatus, setPortfolioStatus] = useState<string>('pending');
  const [totalEvidence, setTotalEvidence] = useState<number>(0);
  const [scanItems, setScanItems] = useState<ScanStatusItem[]>([]);

  useEffect(() => {
    async function initOrFetchScan() {
      if (!portfolioId) {
        // Fallback demo state
        setScanItems([
          {
            repositoryName: 'core-ledger-service',
            commitSha: '7f2d8a4',
            status: 'completed',
            filesProcessed: 28,
            totalFiles: 28,
            skippedSummary: '14 vendor and test fixtures excluded',
            startedAt: '19:14:02 UTC',
            durationMs: 1420,
          },
          {
            repositoryName: 'telemetry-agent',
            commitSha: 'c3e91b0',
            status: 'completed',
            filesProcessed: 12,
            totalFiles: 12,
            skippedSummary: '6 build artifacts excluded',
            startedAt: '19:14:04 UTC',
            durationMs: 980,
          },
          {
            repositoryName: 'data-pipeline-worker',
            commitSha: '91f04b2',
            status: 'completed',
            filesProcessed: 19,
            totalFiles: 19,
            skippedSummary: 'Pytest cache excluded',
            startedAt: '19:14:06 UTC',
            durationMs: 1150,
          },
        ]);
        setPortfolioStatus('completed');
        return;
      }

      setIsLoading(true);
      try {
        let statusRes = await api.getScanStatus(portfolioId);
        if (statusRes.scans.length === 0 || statusRes.portfolio_status === 'pending') {
          // Trigger scan
          setIsScanning(true);
          statusRes = await api.triggerScan(portfolioId);
        }

        setPortfolioStatus(statusRes.portfolio_status);
        setTotalEvidence(statusRes.total_evidence_count);
        setScanItems(
          statusRes.scans.map((s) => ({
            repositoryName: s.repository_name,
            commitSha: s.commit_sha.slice(0, 7),
            status: s.status as any,
            filesProcessed: s.files_processed,
            totalFiles: s.total_files,
            skippedSummary: s.skipped_summary || undefined,
            startedAt: s.started_at,
            durationMs: s.duration_ms || undefined,
          }))
        );
      } catch (err: any) {
        console.warn('Scan status error:', err);
      } finally {
        setIsLoading(false);
        setIsScanning(false);
      }
    }

    initOrFetchScan();
  }, [portfolioId]);

  const handleRescan = async () => {
    if (!portfolioId) return;
    setIsScanning(true);
    try {
      const res = await api.triggerScan(portfolioId);
      setPortfolioStatus(res.portfolio_status);
      setTotalEvidence(res.total_evidence_count);
      setScanItems(
        res.scans.map((s: any) => ({
          repositoryName: s.repository_name,
          commitSha: s.commit_sha.slice(0, 7),
          status: s.status,
          filesProcessed: s.files_processed,
          totalFiles: s.total_files,
          skippedSummary: s.skipped_summary || undefined,
          startedAt: s.started_at,
          durationMs: s.duration_ms,
        }))
      );
    } catch (err: any) {
      console.error('Rescan failed:', err);
    } finally {
      setIsScanning(false);
    }
  };

  const completedCount = scanItems.filter((s) => s.status === 'completed').length;
  const skippedCount = scanItems.filter((s) => s.status === 'partial' || s.status === 'failed').length;

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Portfolio Scan"
        description="Scanning selected repositories for skill evidence."
        badge={portfolioId ? "Live Telemetry" : "Sample Demo"}
        breadcrumbs={[
          { label: 'Repositories', to: '/repositories' },
          { label: 'Job Skills', to: '/jobs/review' },
          { label: 'Scan' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleRescan}
              disabled={isScanning || isLoading}
              className="px-3 py-1.5 rounded-lg border border-[#8CC8F0]/40 text-xs font-medium text-[#142D4E] hover:bg-[#F8FAFC] transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
              <span>Rescan</span>
            </button>
            <button
              onClick={() => navigate('/assessment')}
              className="px-4 py-1.5 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
            >
              <span>View Assessment</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        }
      />

      {/* Progress & Summary Card */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col gap-4">
        {/* Metric pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-[#ECFDF5] border border-[#A7F3D0]">
            <span className="font-mono text-[11px] text-[#047857] font-semibold">COMPLETED</span>
            <span className="font-mono text-xl font-bold text-[#065F46] block mt-0.5">{completedCount}</span>
          </div>

          <div className="p-3 rounded-lg bg-[#E7F3FC] border border-[#8CC8F0]/40">
            <span className="font-mono text-[11px] text-[#27609E] font-semibold">EVIDENCE ITEMS</span>
            <span className="font-mono text-xl font-bold text-[#142D4E] block mt-0.5">{totalEvidence}</span>
          </div>

          <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#CBD5E1]">
            <span className="font-mono text-[11px] text-[#475569] font-semibold">STATUS</span>
            <span className="font-mono text-sm font-bold text-[#1E293B] block mt-1 uppercase">{portfolioStatus}</span>
          </div>

          <div className="p-3 rounded-lg bg-[#FFFBEB] border border-[#FDE68A]">
            <span className="font-mono text-[11px] text-[#B45309] font-semibold">SKIPPED</span>
            <span className="font-mono text-xl font-bold text-[#92400E] block mt-0.5">{skippedCount}</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="flex flex-col gap-1.5 pt-1">
          <div className="flex items-center justify-between text-xs font-mono text-[#44474E]">
            <span>{isScanning ? 'Bounded Scan Running...' : 'Scan Complete'}</span>
            <span className="font-semibold text-[#142D4E]">{isScanning ? 'Processing' : '100%'}</span>
          </div>
          <div className="w-full h-2 bg-[#F2F4F6] rounded-full overflow-hidden border border-[#8CC8F0]/30">
            <div className={`h-full bg-[#3269A8] rounded-full ${isScanning ? 'animate-pulse w-2/3' : 'w-full'}`}></div>
          </div>
        </div>
      </div>

      {/* Scanned Repositories List */}
      <div className="flex flex-col gap-3">
        <h3 className="text-xs font-semibold text-[#142D4E] uppercase tracking-wider font-mono">
          Scanned Repositories
        </h3>

        {scanItems.length === 0 && !isLoading && (
          <div className="p-6 bg-white border border-[#8CC8F0]/30 rounded-xl text-center text-xs text-[#44474E]">
            No scanned repositories yet. Click Rescan to begin bounded evidence extraction.
          </div>
        )}

        <div className="grid grid-cols-1 gap-2.5">
          {scanItems.map((item, idx) => {
            const isDone = item.status === 'completed';

            return (
              <div
                key={idx}
                className="p-3.5 bg-white border border-[#8CC8F0]/40 rounded-xl shadow-xs flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-[#E7F3FC] text-[#3269A8] shrink-0">
                    <FolderGit2 className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#142D4E] truncate">
                        {item.repositoryName}
                      </span>
                      <span className="text-[11px] font-mono text-[#74777F] flex items-center gap-1">
                        <GitCommit className="w-3 h-3 text-[#3269A8]" />
                        {item.commitSha}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-[#44474E] pt-0.5">
                      <span>{item.filesProcessed} files processed</span>
                      {item.durationMs && <span>· {item.durationMs}ms</span>}
                      {item.skippedSummary && (
                        <span className="text-[#B45309] font-mono text-[11px]">
                          ({item.skippedSummary})
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isDone ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#059669]" />
                      <span>Completed</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A]">
                      <AlertTriangle className="w-3.5 h-3.5 text-[#D97706]" />
                      <span>{item.status}</span>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
