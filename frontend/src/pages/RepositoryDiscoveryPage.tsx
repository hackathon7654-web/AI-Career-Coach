import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { EmptyState } from '../components/common/EmptyState';
import {
  FolderGit2,
  ExternalLink,
  GitBranch,
  RefreshCw,
  Clock,
  ArrowRight,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import type { RepositorySummary } from '../types';
import { api, sessionStore } from '../api/client';

export const RepositoryDiscoveryPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryUser = searchParams.get('user');
  const [resolvedHandle, setResolvedHandle] = useState<string>(queryUser || 'sample-engineer');
  const paramPid = searchParams.get('pid') || sessionStore.getPortfolioId();

  useEffect(() => {
    if (!queryUser) {
      api.getSession()
        .then((sess) => {
          if (sess?.authenticated && sess?.github_username) {
            setResolvedHandle(sess.github_username);
          }
        })
        .catch(() => {});
    }
  }, [queryUser]);

  const [activeTab, setActiveTab] = useState<'discovered' | 'empty' | 'ratelimit' | 'error'>('discovered');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Discovered repositories state
  const [repositories, setRepositories] = useState<Array<RepositorySummary & { id?: string }>>([]);
  const [selectedRepos, setSelectedRepos] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function loadRepos() {
      if (!paramPid) {
        // Fallback to sample baseline if no intake session
        return;
      }
      setIsLoading(true);
      setErrorMessage('');
      try {
        const res = await api.discoverRepositories(paramPid);
        const mapped = res.repositories.map((r) => ({
          id: r.id,
          name: r.name,
          url: r.html_url,
          description: r.description || '',
          defaultBranch: r.default_branch,
          lastCommitSha: r.last_commit_sha || 'latest',
          isEligible: r.is_eligible,
          skipReason: r.skip_reason,
          language: r.language || 'Code',
          stars: r.stars,
          is_selected: r.is_selected,
        }));
        setRepositories(mapped);

        if (mapped.length === 0) {
          setActiveTab('empty');
        } else {
          setActiveTab('discovered');
          const sel: Record<string, boolean> = {};
          mapped.forEach((r) => {
            if (r.isEligible && r.is_selected) {
              sel[r.name] = true;
            }
          });
          setSelectedRepos(sel);
        }
      } catch (err: any) {
        if (err.status === 429) {
          setActiveTab('ratelimit');
        } else {
          setActiveTab('error');
          setErrorMessage(err.message || 'Failed to discover repositories.');
        }
      } finally {
        setIsLoading(false);
      }
    }

    loadRepos();
  }, [paramPid]);

  const eligibleRepos = repositories.filter((r) => r.isEligible);
  const selectedCount = Object.values(selectedRepos).filter(Boolean).length;

  const toggleSelectAll = (select: boolean) => {
    const updated: Record<string, boolean> = {};
    eligibleRepos.forEach((r) => {
      updated[r.name] = select;
    });
    setSelectedRepos(updated);
  };

  const handleCheckboxToggle = (repoName: string) => {
    setSelectedRepos((prev) => ({
      ...prev,
      [repoName]: !prev[repoName],
    }));
  };

  const handleProceed = async () => {
    if (!paramPid) {
      navigate('/jobs/new');
      return;
    }

    // Collect database repository IDs of selected repos
    const selectedIds = repositories
      .filter((r) => r.id && selectedRepos[r.name])
      .map((r) => r.id as string);

    if (selectedIds.length > 0) {
      setIsSaving(true);
      try {
        await api.selectRepositories(paramPid, selectedIds);
      } catch (err: any) {
        console.warn('Repository selection update non-blocking:', err);
      } finally {
        setIsSaving(false);
      }
    }

    navigate('/jobs/new');
  };

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Choose Repositories"
        description="Select which repositories to scan for evidence."
        badge={paramPid ? "Verified Session" : "Sample Demo"}
        breadcrumbs={[
          { label: 'GitHub Portfolio', to: '/' },
          { label: 'Repositories' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Link
              to="/"
              className="px-3 py-1.5 rounded-lg border border-[#8CC8F0]/40 text-xs font-medium text-[#142D4E] hover:bg-[#F8FAFC] transition-colors"
            >
              Change Account
            </Link>
            <button
              onClick={handleProceed}
              disabled={selectedCount === 0 || isSaving}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold text-white transition-colors flex items-center gap-1.5 shadow-xs ${
                selectedCount > 0 && !isSaving
                  ? 'bg-[#3269A8] hover:bg-[#275488] cursor-pointer'
                  : 'bg-[#74777F] opacity-50 cursor-not-allowed'
              }`}
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <span>Continue ({selectedCount})</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        }
      />

      {/* Subtle State Switcher */}
      <div className="flex items-center gap-2 self-start text-xs font-mono">
        <span className="text-[#74777F]">View:</span>
        <button
          onClick={() => setActiveTab('discovered')}
          className={`px-2 py-0.5 rounded transition-colors ${
            activeTab === 'discovered'
              ? 'bg-[#142D4E] text-white font-medium'
              : 'text-[#44474E] hover:text-[#142D4E]'
          }`}
        >
          Discovered ({repositories.length})
        </button>
        <button
          onClick={() => setActiveTab('empty')}
          className={`px-2 py-0.5 rounded transition-colors ${
            activeTab === 'empty'
              ? 'bg-[#142D4E] text-white font-medium'
              : 'text-[#44474E] hover:text-[#142D4E]'
          }`}
        >
          Empty
        </button>
        <button
          onClick={() => setActiveTab('ratelimit')}
          className={`px-2 py-0.5 rounded transition-colors ${
            activeTab === 'ratelimit'
              ? 'bg-[#142D4E] text-white font-medium'
              : 'text-[#44474E] hover:text-[#142D4E]'
          }`}
        >
          Rate Limit
        </button>
        <button
          onClick={() => setActiveTab('error')}
          className={`px-2 py-0.5 rounded transition-colors ${
            activeTab === 'error'
              ? 'bg-[#142D4E] text-white font-medium'
              : 'text-[#44474E] hover:text-[#142D4E]'
          }`}
        >
          Error
        </button>
      </div>

      {isLoading && (
        <div className="p-12 flex flex-col items-center justify-center gap-3 bg-white border border-[#8CC8F0]/30 rounded-xl">
          <Loader2 className="w-6 h-6 text-[#3269A8] animate-spin" />
          <p className="text-xs text-[#44474E]">Discovering public GitHub repositories for @{resolvedHandle}...</p>
        </div>
      )}

      {/* VIEW: DISCOVERED REPOSITORIES */}
      {!isLoading && activeTab === 'discovered' && (
        <div className="flex flex-col gap-4">
          {/* Selection Control Bar */}
          <div className="flex items-center justify-between p-3.5 bg-white border border-[#8CC8F0]/40 rounded-xl shadow-xs">
            <label className="flex items-center gap-2 text-xs font-medium text-[#142D4E] cursor-pointer">
              <input
                type="checkbox"
                checked={selectedCount === eligibleRepos.length && eligibleRepos.length > 0}
                onChange={(e) => toggleSelectAll(e.target.checked)}
                className="rounded border-[#8CC8F0] text-[#3269A8] focus:ring-[#8CC8F0]"
              />
              <span>Select All Eligible ({eligibleRepos.length})</span>
            </label>
            <span className="text-xs font-mono text-[#44474E]">
              {selectedCount} of {eligibleRepos.length} selected
            </span>
          </div>

          {/* Repository Cards */}
          <div className="grid grid-cols-1 gap-3">
            {repositories.map((repo) => {
              const isSelected = !!selectedRepos[repo.name];

              return (
                <div
                  key={repo.name}
                  onClick={() => repo.isEligible && handleCheckboxToggle(repo.name)}
                  className={`p-4 rounded-xl border transition-all ${
                    !repo.isEligible
                      ? 'bg-[#F8FAFC] border-dashed border-[#8CC8F0]/30 opacity-70'
                      : isSelected
                      ? 'bg-white border-[#3269A8] shadow-xs cursor-pointer'
                      : 'bg-white border-[#8CC8F0]/40 hover:border-[#8CC8F0] cursor-pointer'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={!repo.isEligible}
                        onChange={() => {}}
                        className="mt-1 rounded border-[#8CC8F0] text-[#3269A8] focus:ring-[#8CC8F0]"
                      />

                      <div className="flex flex-col gap-1 min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <FolderGit2 className="w-4 h-4 text-[#3269A8] shrink-0" />
                          <span className="font-semibold text-sm text-[#142D4E] truncate">
                            {repo.name}
                          </span>
                          <span className="text-xs text-[#74777F] font-mono">
                            {repo.language}
                          </span>
                          {!repo.isEligible && (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-[#FFFBEB] text-[#B45309] border border-[#FDE68A]">
                              {repo.skipReason}
                            </span>
                          )}
                        </div>

                        <p className="text-xs text-[#44474E] line-clamp-1">
                          {repo.description}
                        </p>

                        <div className="flex items-center gap-3 text-xs font-mono text-[#74777F] pt-1">
                          <span className="flex items-center gap-1">
                            <GitBranch className="w-3 h-3 text-[#3269A8]" />
                            {repo.defaultBranch}
                          </span>
                          <span>Commit {(repo.lastCommitSha || 'latest').slice(0, 7)}</span>
                          <span>★ {repo.stars}</span>
                        </div>
                      </div>
                    </div>

                    <a
                      href={repo.url}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="p-1 text-[#74777F] hover:text-[#3269A8] transition-colors"
                      title="View on GitHub"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* VIEW: EMPTY STATE */}
      {!isLoading && activeTab === 'empty' && (
        <EmptyState
          icon={<FolderGit2 className="w-6 h-6" />}
          title="No eligible repositories found"
          description={`We couldn't find any public repositories for ${resolvedHandle} that meet scanning qualification criteria.`}
          action={
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg"
            >
              Try another account
            </button>
          }
        />
      )}

      {/* VIEW: RATE LIMIT REACHED */}
      {!isLoading && activeTab === 'ratelimit' && (
        <div className="p-8 bg-white border border-[#FDE68A] rounded-xl flex flex-col items-center text-center gap-3 shadow-xs">
          <Clock className="w-8 h-8 text-[#D97706]" />
          <h2 className="font-semibold text-base text-[#142D4E]">
            GitHub API Rate Limit Reached
          </h2>
          <p className="text-xs text-[#44474E] max-w-md">
            GitHub limits unauthenticated API requests to 60/hr per IP. Please wait a few moments or try again later.
          </p>
          <div className="pt-2">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg flex items-center gap-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Discovery</span>
            </button>
          </div>
        </div>
      )}

      {/* VIEW: GENERIC ERROR */}
      {!isLoading && activeTab === 'error' && (
        <div className="p-8 bg-white border border-[#BA1A1A]/30 rounded-xl flex flex-col items-center text-center gap-3 shadow-xs">
          <AlertCircle className="w-8 h-8 text-[#BA1A1A]" />
          <h2 className="font-semibold text-base text-[#142D4E]">
            Repository Discovery Error
          </h2>
          <p className="text-xs text-[#BA1A1A] max-w-md">
            {errorMessage || 'Failed to fetch repositories from GitHub.'}
          </p>
          <div className="pt-2">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-[#142D4E] hover:bg-[#1D3F66] text-white text-xs font-semibold rounded-lg flex items-center gap-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Try Again</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
