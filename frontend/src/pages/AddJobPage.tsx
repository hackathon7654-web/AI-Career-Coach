import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  Link as LinkIcon,
  FileText,
  AlertCircle,
  ArrowRight,
  RotateCcw,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { api, sessionStore } from '../api/client';

export const AddJobPage = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'url' | 'paste'>('paste');
  const [jobUrl, setJobUrl] = useState('');
  const [pastedText, setPastedText] = useState(
    `Role: Staff Backend Systems Engineer
Company: Applied Systems Inc.

Requirements:
- Strong proficiency in Go or TypeScript for high-throughput distributed backend services.
- Experience building event-driven microservices with message queues (RabbitMQ, Apache Kafka, or SQS).
- Hands-on database schema design, transactional SQL migrations, and query optimization on PostgreSQL.
- Solid understanding of Docker containerization and CI/CD pipelines (GitHub Actions).
- Proven ability to write comprehensive automated unit and integration tests.

Preferred / Differentiators:
- Experience implementing Kubernetes Operators and Custom Resource Definitions (CRDs).
- Hands-on eBPF-based network tracing or performance profiling.
- Distributed tracing and metric instrumentation using OpenTelemetry (OTel).`
  );

  const [errorMessage, setErrorMessage] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [hasActiveSession, setHasActiveSession] = useState(true);
  const [sessionUsername, setSessionUsername] = useState<string | null>(null);

  useEffect(() => {
    async function checkSession() {
      try {
        const sess = await api.getSession();
        if (sess && sess.portfolio_id) {
          sessionStore.setPortfolioId(sess.portfolio_id);
          setHasActiveSession(true);
          setSessionUsername(sess.github_username || null);
        } else {
          setHasActiveSession(false);
        }
      } catch {
        const pid = sessionStore.getPortfolioId();
        setHasActiveSession(Boolean(pid));
      } finally {
        setSessionChecked(true);
      }
    }
    checkSession();
  }, []);

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobUrl.trim()) return;

    if (!hasActiveSession) {
      setErrorMessage('Please connect your GitHub profile on Screen 1 before ingesting a job.');
      return;
    }

    setIsExtracting(true);
    setErrorMessage('');
    try {
      const pid = sessionStore.getPortfolioId() || undefined;
      const res = await api.createJob({ job_url: jobUrl.trim(), portfolio_id: pid });
      sessionStore.setJobId(res.id);
      navigate(`/jobs/review?job_id=${encodeURIComponent(res.id)}`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch job URL. Please try pasting the text.');
    } finally {
      setIsExtracting(false);
    }
  };

  const handlePasteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pastedText.trim()) return;

    if (!hasActiveSession) {
      setErrorMessage('Please connect your GitHub profile on Screen 1 before ingesting a job.');
      return;
    }

    setIsExtracting(true);
    setErrorMessage('');
    try {
      const pid = sessionStore.getPortfolioId() || undefined;
      const res = await api.createJob({ pasted_text: pastedText.trim(), portfolio_id: pid });
      sessionStore.setJobId(res.id);
      navigate(`/jobs/review?job_id=${encodeURIComponent(res.id)}`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to ingest job description.');
    } finally {
      setIsExtracting(false);
    }
  };

  const charCount = pastedText.length;

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Add Target Job"
        description="Add a job description to identify required skills."
        breadcrumbs={[
          { label: 'Repositories', to: '/repositories' },
          { label: 'Target Job' },
        ]}
      />

      {/* Session State Alerts */}
      {!hasActiveSession && sessionChecked && (
        <div className="bg-[#FFFBEB] border border-[#FDE68A] rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs sm:text-sm text-[#92400E]">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-[#D97706] shrink-0" />
            <span>
              <strong>No active intake session:</strong> Please connect your GitHub account on Screen 1 before submitting a target job.
            </span>
          </div>
          <button
            onClick={() => navigate('/')}
            className="px-3 py-1.5 rounded-lg bg-[#142D4E] text-white hover:bg-[#1E4273] font-medium transition-colors shrink-0 cursor-pointer"
          >
            Connect GitHub
          </button>
        </div>
      )}

      {hasActiveSession && sessionUsername && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#E7F3FC]/60 border border-[#8CC8F0]/30 text-xs text-[#27609E] w-fit">
          <CheckCircle2 className="w-3.5 h-3.5 text-[#3269A8]" />
          <span>Verified candidate session active for <strong>@{sessionUsername}</strong></span>
        </div>
      )}

      {/* Mode Selector Tabs */}
      <div className="flex items-center gap-2 border-b border-[#8CC8F0]/30 pb-3">
        <button
          onClick={() => {
            setMode('paste');
            setErrorMessage('');
          }}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer ${
            mode === 'paste'
              ? 'bg-[#142D4E] text-white shadow-xs'
              : 'bg-[#F2F4F6] text-[#44474E] hover:bg-[#E7F3FC]'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Paste Description</span>
          {charCount > 0 && (
            <span className="font-mono text-[11px] bg-[#3269A8] px-1.5 rounded text-white">
              Sample
            </span>
          )}
        </button>

        <button
          onClick={() => {
            setMode('url');
            setErrorMessage('');
          }}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer ${
            mode === 'url'
              ? 'bg-[#142D4E] text-white shadow-xs'
              : 'bg-[#F2F4F6] text-[#44474E] hover:bg-[#E7F3FC]'
          }`}
        >
          <LinkIcon className="w-4 h-4" />
          <span>Job URL</span>
        </button>
      </div>

      {/* PASTE MODE (DEFAULT) */}
      {mode === 'paste' && (
        <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-6 shadow-xs flex flex-col gap-4">
          <form onSubmit={handlePasteSubmit} className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <label htmlFor="raw-job-text" className="text-xs font-semibold text-[#142D4E]">
                Job Description
              </label>
              <button
                type="button"
                onClick={() => setPastedText('')}
                className="font-mono text-xs text-[#74777F] hover:text-[#BA1A1A] flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Clear</span>
              </button>
            </div>

            <textarea
              id="raw-job-text"
              rows={9}
              disabled={isExtracting}
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              placeholder="Paste job posting requirements and expectations..."
              className="w-full p-3.5 bg-[#F8FAFC] border border-[#8CC8F0]/60 text-[#142D4E] rounded-lg text-xs sm:text-sm font-sans focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#8CC8F0] leading-relaxed resize-y disabled:opacity-60"
            />

            <div className="flex items-center justify-between pt-1">
              <span className="font-mono text-xs text-[#74777F]">
                {charCount.toLocaleString()} characters
              </span>
              <button
                type="submit"
                disabled={isExtracting || !pastedText.trim()}
                className={`px-5 py-2.5 rounded-lg text-xs font-semibold text-white transition-colors flex items-center justify-center gap-2 shadow-xs ${
                  pastedText.trim() && !isExtracting
                    ? 'bg-[#3269A8] hover:bg-[#275488] cursor-pointer'
                    : 'bg-[#74777F] opacity-50 cursor-not-allowed'
                }`}
              >
                {isExtracting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Extracting...</span>
                  </>
                ) : (
                  <>
                    <span>Extract Requirements</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>

          {errorMessage && (
            <div className="p-3 rounded-lg bg-[#FEE2E2] border border-[#FCA5A5] flex items-center gap-2 text-xs text-[#991B1B]">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      )}

      {/* URL MODE */}
      {mode === 'url' && (
        <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-6 shadow-xs flex flex-col gap-4">
          <form onSubmit={handleUrlSubmit} className="flex flex-col gap-4">
            <label htmlFor="job-url" className="text-xs font-semibold text-[#142D4E]">
              Public Job URL
            </label>

            <div className="flex flex-col sm:flex-row items-stretch gap-2.5">
              <input
                id="job-url"
                type="url"
                disabled={isExtracting}
                value={jobUrl}
                onChange={(e) => {
                  setJobUrl(e.target.value);
                  if (errorMessage) setErrorMessage('');
                }}
                placeholder="https://company.com/careers/job-id"
                className="flex-1 px-3.5 py-2.5 bg-[#F8FAFC] border border-[#8CC8F0]/60 text-[#142D4E] rounded-lg text-xs sm:text-sm focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#8CC8F0] placeholder:text-[#74777F] disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={isExtracting || !jobUrl.trim()}
                className={`px-5 py-2.5 rounded-lg text-xs font-semibold text-white transition-colors flex items-center justify-center gap-2 shadow-xs ${
                  jobUrl.trim() && !isExtracting
                    ? 'bg-[#3269A8] hover:bg-[#275488] cursor-pointer'
                    : 'bg-[#74777F] opacity-50 cursor-not-allowed'
                }`}
              >
                {isExtracting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Extracting...</span>
                  </>
                ) : (
                  <>
                    <span>Extract Requirements</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>

          {errorMessage && (
            <div className="p-3 rounded-lg bg-[#FFFBEB] border border-[#FDE68A] flex items-center justify-between gap-3 text-xs text-[#B45309]">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0" />
                <span>{errorMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setMode('paste')}
                className="underline font-medium hover:text-[#78350F] cursor-pointer"
              >
                Switch to Paste
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
