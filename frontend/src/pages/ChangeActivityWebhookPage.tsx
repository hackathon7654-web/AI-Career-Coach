import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  GitBranch,
  Copy,
  Check,
  RefreshCw,
  GitCommit,
  ArrowRight,
  Send,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  AlertCircle,
  FileCode,
} from 'lucide-react';
import type { WebhookDelivery } from '../types';
import { api, sessionStore, API_BASE } from '../api/client';

export const ChangeActivityWebhookPage = () => {
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [isPinging, setIsPinging] = useState(false);
  const [pingSuccess, setPingSuccess] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trackedRepos, setTrackedRepos] = useState<string[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');

  const portfolioId = sessionStore.getPortfolioId();
  const payloadUrl = `${API_BASE}/api/webhooks/github`;

  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);

  const fetchActivity = async () => {
    if (!portfolioId) {
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      setError(null);

      // Fetch candidate repositories for simulator target
      try {
        const repoRes = await api.discoverRepositories(portfolioId);
        if (repoRes && repoRes.repositories && repoRes.repositories.length > 0) {
          const names = repoRes.repositories.map((r: any) => r.full_name);
          setTrackedRepos(names);
          if (!selectedRepo && names.length > 0) {
            setSelectedRepo(names[0]);
          }
        }
      } catch (e) {
        // Fallback repo name if discovery call fails
      }

      const res = await api.getActivity(portfolioId);
      if (res && res.deliveries) {
        const mapped: WebhookDelivery[] = res.deliveries.map((d: any) => ({
          deliveryId: d.delivery_id,
          repositoryName: d.repository_name,
          commitSha: d.commit_sha ? d.commit_sha.slice(0, 7) : 'unknown',
          eventType: d.event_type || 'push',
          changedPaths: d.changed_paths || [],
          receivedAt: d.received_at
            ? new Date(d.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' UTC'
            : 'recent',
          hmacVerified: Boolean(d.hmac_verified),
          reassessmentStatus: d.status || 'completed',
          retryCount: d.retry_count || 0,
          reassessmentRunId: d.reassessment_run_id,
          errorDetails: d.error_details,
        }));
        setDeliveries(mapped);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load activity ledger.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchActivity();
  }, [portfolioId]);

  const handleCopy = (textToCopy?: string) => {
    navigator.clipboard.writeText(textToCopy || payloadUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  const handleSimulatePush = async () => {
    if (!portfolioId) return;
    const targetRepo = selectedRepo || (trackedRepos.length > 0 ? trackedRepos[0] : 'demo/core-service');

    setIsPinging(true);
    setError(null);
    try {
      await api.simulatePush(portfolioId, {
        repository_name: targetRepo,
        commit_message: 'Update implementation logic for skill evaluation',
        changed_paths: ['src/services/handler.ts'],
      });
      setPingSuccess(true);
      await fetchActivity();
      setTimeout(() => setPingSuccess(false), 3000);
    } catch (err: any) {
      setError(err?.message || 'Push simulation failed.');
    } finally {
      setIsPinging(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="GitHub Activity & Webhook Ledger"
        description="Automatic re-evaluation when new commits are pushed."
        badge="Active (Phase 3G)"
        breadcrumbs={[
          { label: 'Assessment', to: '/assessment' },
          { label: 'GitHub Activity' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={fetchActivity}
              disabled={isLoading}
              className="px-3 py-1.5 border border-[#8CC8F0]/40 text-[#3269A8] hover:bg-[#F0F8FF] text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
            <Link
              to="/history"
              className="px-4 py-1.5 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs"
            >
              <span>Assessment History</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        }
      />

      {error && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Simulator Control Card */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-[#3269A8]" />
              <h3 className="text-sm font-semibold text-[#142D4E]">
                Push Event Simulator (Local Verification)
              </h3>
            </div>
            <p className="text-xs text-[#74777F] mt-0.5">
              Simulate an inbound commit push to trigger bounded scanning, evidence refresh, and automatic job reassessment.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {trackedRepos.length > 0 && (
              <select
                value={selectedRepo}
                onChange={(e) => setSelectedRepo(e.target.value)}
                className="text-xs border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 bg-[#F8FAFC] text-[#142D4E] font-mono outline-hidden focus:border-[#3269A8]"
              >
                {trackedRepos.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            )}

            <button
              onClick={handleSimulatePush}
              disabled={isPinging || !portfolioId}
              className={`px-4 py-2 rounded-lg text-xs font-semibold text-white transition-colors flex items-center justify-center gap-2 shadow-xs ${
                isPinging
                  ? 'bg-[#74777F] opacity-75 cursor-not-allowed'
                  : pingSuccess
                  ? 'bg-[#047857]'
                  : 'bg-[#3269A8] hover:bg-[#275488] cursor-pointer'
              }`}
            >
              {isPinging ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Scanning & Reassessing...</span>
                </>
              ) : pingSuccess ? (
                <span>Reassessment Snapshot Created!</span>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Simulate Push Event</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Setup Details */}
        <div className="pt-2 border-t border-[#8CC8F0]/20">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-1 text-xs text-[#3269A8] hover:underline cursor-pointer"
          >
            {showDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            <span>Webhook Integration Details</span>
          </button>

          {showDetails && (
            <div className="mt-3 p-3.5 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/30 text-xs flex flex-col gap-3 font-mono">
              <div className="flex flex-col gap-1.5 p-2.5 rounded bg-white border border-[#CBD5E1]/60">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-[#142D4E]">GitHub.com Payload URL:</span>
                    <span className="text-[10px] bg-[#E7F3FC] text-[#3269A8] px-1.5 py-0.5 rounded font-sans font-medium">
                      Public HTTPS Required
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-[#142D4E]">
                    <span className="break-all font-semibold text-[#047857]">
                      {window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
                        ? 'https://<your-tunnel-host>/api/webhooks/github'
                        : `${window.location.origin}/api/webhooks/github`}
                    </span>
                    <button
                      onClick={() => {
                        const target = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
                          ? 'https://<your-tunnel-host>/api/webhooks/github'
                          : `${window.location.origin}/api/webhooks/github`;
                        handleCopy(target);
                      }}
                      className="p-1 hover:text-[#3269A8] cursor-pointer"
                      title="Copy Public Webhook Path"
                    >
                      {copiedUrl ? <Check className="w-3.5 h-3.5 text-[#047857]" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
                <p className="text-[11px] text-[#74777F] font-sans">
                  GitHub requires a public HTTPS URL (e.g. via <code>ngrok http 8000</code>). GitHub.com cannot reach <code>localhost</code>.
                </p>
              </div>

              <div className="flex items-center justify-between flex-wrap gap-2 text-[#74777F]">
                <span>Local Loopback (Dev / Simulator):</span>
                <span className="text-[#44474E]">{payloadUrl}</span>
              </div>
              <div className="flex items-center justify-between text-[#74777F]">
                <span>Secret & Signature verification:</span>
                <span className="text-[#047857] flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> HMAC-SHA256 (Server-side enforced)
                </span>
              </div>
              <div className="flex items-center justify-between text-[#74777F]">
                <span>Idempotency & Deduplication:</span>
                <span>Enforced via X-GitHub-Delivery header</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Deliveries List */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-[#142D4E] uppercase tracking-wider font-mono">
            Recent Activity Ledger ({deliveries.length})
          </h3>
          <span className="text-xs text-[#74777F]">
            {deliveries.filter((d) => d.hmacVerified).length} verified webhook{deliveries.filter((d) => d.hmacVerified).length === 1 ? '' : 's'}
          </span>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-xs text-[#74777F] bg-white border border-[#8CC8F0]/30 rounded-xl">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-[#3269A8] mb-2" />
            Loading persisted activity records...
          </div>
        ) : deliveries.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#74777F] bg-white border border-[#8CC8F0]/30 rounded-xl">
            <GitCommit className="w-6 h-6 mx-auto text-[#74777F] mb-2 opacity-60" />
            No repository deliveries recorded yet. Push commits or use the simulator above to trigger an evidence refresh.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2.5">
            {deliveries.map((del, idx) => (
              <div
                key={del.deliveryId || idx}
                className="bg-white border border-[#8CC8F0]/40 rounded-xl p-3.5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="flex items-start sm:items-center gap-3 min-w-0">
                  <div className={`p-2 rounded-lg shrink-0 ${del.hmacVerified ? 'bg-[#ECFDF5] text-[#047857]' : 'bg-[#E7F3FC] text-[#3269A8]'}`}>
                    <GitCommit className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-semibold text-[#142D4E]">
                        {del.repositoryName}
                      </span>
                      <span className="font-mono text-xs text-[#3269A8] bg-[#E7F3FC] px-1.5 py-0.5 rounded">
                        {del.commitSha}
                      </span>
                      {del.reassessmentRunId && (
                        <Link
                          to={`/history`}
                          className="font-mono text-[11px] text-[#047857] hover:underline flex items-center gap-0.5"
                          title="View Assessment Run"
                        >
                          <span>Snapshot updated</span>
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      )}
                    </div>
                    {del.changedPaths.length > 0 && (
                      <div className="flex items-center gap-1 mt-1 text-[#74777F] text-xs font-mono truncate">
                        <FileCode className="w-3 h-3 shrink-0" />
                        <span className="truncate">{del.changedPaths.join(', ')}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 font-mono text-xs justify-between sm:justify-end">
                  {del.hmacVerified ? (
                    <span className="px-2 py-0.5 rounded bg-[#ECFDF5] text-[#047857] border border-[#A7F3D0] text-[11px] font-semibold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> Verified Webhook
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded bg-[#F8FAFC] text-[#44474E] border border-[#CBD5E1]/60 text-[11px]">
                      Local Simulation
                    </span>
                  )}
                  <span className="text-[#74777F] text-[11px]">{del.receivedAt}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
