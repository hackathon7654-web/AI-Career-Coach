import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Info, GitBranch, Loader2, ArrowRight, CheckCircle2 } from 'lucide-react';
import { api, sessionStore } from '../api/client';

export const PortfolioStartPage = () => {
  const navigate = useNavigate();
  const [profileInput, setProfileInput] = useState('');
  const [validationError, setValidationError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [existingSession, setExistingSession] = useState<{
    authenticated: boolean;
    portfolio_id: string;
    github_username: string;
  } | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function checkSession() {
      try {
        const sess = await api.getSession();
        if (isMounted && sess && sess.authenticated && sess.portfolio_id) {
          setExistingSession(sess);
          sessionStore.setPortfolioId(sess.portfolio_id);
        }
      } catch {
        // No active session or unauthenticated, prompt form
      }
    }
    checkSession();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = profileInput.trim();
    if (!trimmed) {
      setValidationError('Please enter a GitHub profile URL or username.');
      return;
    }
    setValidationError('');
    const cleanHandle = trimmed.replace(/^https?:\/\/github\.com\//, '').replace(/\/$/, '');

    setIsLoading(true);
    try {
      const res = await api.createIntake(cleanHandle);
      sessionStore.setPortfolioId(res.portfolio_id);
      navigate(`/repositories?user=${encodeURIComponent(cleanHandle)}&pid=${encodeURIComponent(res.portfolio_id)}`);
    } catch (err: any) {
      setValidationError(err.message || 'Failed to initialize portfolio intake session.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickTry = async (handle: string) => {
    setProfileInput(handle);
    setValidationError('');
    setIsLoading(true);
    try {
      const res = await api.createIntake(handle);
      sessionStore.setPortfolioId(res.portfolio_id);
      navigate(`/repositories?user=${encodeURIComponent(handle)}&pid=${encodeURIComponent(res.portfolio_id)}`);
    } catch (err: any) {
      setValidationError(err.message || 'Failed to initialize portfolio session.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto flex flex-col gap-6">
      {/* Title & Core Subtitle */}
      <div className="flex flex-col gap-2 text-center sm:text-left">
        <div className="inline-flex items-center gap-1.5 self-center sm:self-start px-2.5 py-0.5 rounded-full bg-[#E7F3FC] border border-[#8CC8F0]/40 text-xs font-mono text-[#27609E]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#3269A8]"></span>
          <span>Verified Intake Session</span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#142D4E]">
          Connect your GitHub
        </h1>

        <p className="text-sm sm:text-base text-[#44474E] leading-relaxed">
          Match your skills to a job using code from your GitHub repositories.
        </p>
      </div>

      {/* Active Session Notification */}
      {existingSession && (
        <div className="bg-[#ECFDF5] border border-[#A7F3D0] rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#10B981] text-white flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm text-[#065F46]">
                  Active Session Connected
                </span>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-[#D1FAE5] text-[#047857] border border-[#6EE7B7]">
                  @{existingSession.github_username}
                </span>
              </div>
              <p className="text-xs text-[#047857] mt-0.5">
                Your portfolio intake session is authenticated and ready to scan repositories.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                navigate(
                  `/repositories?user=${encodeURIComponent(existingSession.github_username)}&pid=${encodeURIComponent(existingSession.portfolio_id)}`
                );
              }}
              className="px-4 py-2 bg-[#047857] hover:bg-[#065F46] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
            >
              <span>Continue as @{existingSession.github_username}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Main Intake Form */}
      <div className="bg-[#FFFFFF] border border-[#8CC8F0]/40 rounded-xl p-6 sm:p-8 shadow-xs flex flex-col gap-5">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label htmlFor="github-handle" className="text-sm font-semibold text-[#142D4E]">
            GitHub profile or username
          </label>

          <div className="flex flex-col sm:flex-row items-stretch gap-2.5">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#74777F]">
                <GitBranch className="w-4 h-4 text-[#74777F]" />
              </div>
              <input
                id="github-handle"
                type="text"
                disabled={isLoading}
                value={profileInput}
                onChange={(e) => {
                  setProfileInput(e.target.value);
                  if (validationError) setValidationError('');
                }}
                placeholder="e.g. sample-engineer or your-username"
                className="w-full pl-10 pr-4 py-2.5 bg-[#F8FAFC] border border-[#8CC8F0]/60 text-[#142D4E] rounded-lg font-sans text-sm focus:outline-none focus:bg-[#FFFFFF] focus:ring-2 focus:ring-[#8CC8F0] placeholder:text-[#74777F] disabled:opacity-60"
                spellCheck={false}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="px-5 py-2.5 bg-[#3269A8] hover:bg-[#275488] active:bg-[#1D3F66] text-white font-semibold text-sm rounded-lg transition-colors flex items-center justify-center gap-2 shadow-xs cursor-pointer whitespace-nowrap disabled:opacity-60"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Find Repositories</span>
                </>
              )}
            </button>
          </div>

          {validationError && (
            <p className="text-xs text-[#BA1A1A] font-medium">{validationError}</p>
          )}

          {/* Quick-try sample option */}
          <div className="flex items-center gap-2 pt-1 text-xs text-[#44474E] flex-wrap">
            <span className="text-[#74777F]">Sample profile:</span>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => handleQuickTry('sample-engineer')}
              className="px-2.5 py-1 rounded bg-[#E7F3FC] text-[#27609E] hover:bg-[#D7EAF8] font-mono text-xs font-medium transition-colors cursor-pointer disabled:opacity-60"
            >
              sample-engineer
            </button>
          </div>
        </form>
      </div>

      {/* Principle Note */}
      <div className="p-3.5 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/30 flex items-start gap-2.5 text-xs text-[#44474E]">
        <Info className="w-4 h-4 text-[#3269A8] shrink-0 mt-0.5" />
        <p>
          <strong className="text-[#142D4E]">Note:</strong> Missing repository evidence does not mean you lack a skill. ProofPath only evaluates code in selected repositories.
        </p>
      </div>
    </div>
  );
};
