import { useState, useEffect } from 'react';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  Link as LinkIcon,
  ShieldCheck,
  CheckCircle2,
  Folder,
  Save,
  RefreshCw,
} from 'lucide-react';
import { api } from '../api/client';

export const SettingsPage = () => {
  const [maxFileSize, setMaxFileSize] = useState('1.0');
  const [defaultBranch, setDefaultBranch] = useState('default');
  const [autoReassess, setAutoReassess] = useState(true);
  const [savedNotification, setSavedNotification] = useState(false);
  const [githubStatus, setGithubStatus] = useState<'loading' | 'configured' | 'unauthenticated'>('loading');
  const [activeSessionUser, setActiveSessionUser] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const [health, session] = await Promise.allSettled([
        api.getHealth(),
        api.getSession(),
      ]);
      if (health.status === 'fulfilled') {
        setGithubStatus(health.value.github === 'configured' ? 'configured' : 'unauthenticated');
      } else {
        setGithubStatus('unauthenticated');
      }
      if (session.status === 'fulfilled' && session.value.authenticated) {
        setActiveSessionUser(session.value.github_username);
      }
    } catch {
      setGithubStatus('unauthenticated');
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSave = () => {
    setSavedNotification(true);
    setTimeout(() => setSavedNotification(false), 2500);
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Settings"
        description="Manage your repository and scan preferences."
        badge={githubStatus === 'configured' ? 'Live Connected' : 'Demo Mode'}
        actions={
          <button
            onClick={handleSave}
            className="px-4 py-1.5 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Preferences</span>
          </button>
        }
      />

      {savedNotification && (
        <div className="p-3 bg-[#ECFDF5] border border-[#A7F3D0] rounded-xl text-xs text-[#047857] font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
          <span>Preferences saved to local browser session.</span>
        </div>
      )}

      {/* GitHub Connection */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LinkIcon className="w-4 h-4 text-[#3269A8]" />
            <h3 className="text-xs font-semibold text-[#142D4E] uppercase tracking-wider font-mono">
              GitHub Connection
            </h3>
          </div>
          <button
            onClick={fetchStatus}
            title="Refresh status"
            className="p-1 text-[#74777F] hover:text-[#3269A8] transition-colors rounded cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="p-3 bg-[#F8FAFC] rounded-lg border border-[#8CC8F0]/30 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <div
              className={`w-8 h-8 rounded-full text-white flex items-center justify-center font-bold text-xs ${
                githubStatus === 'configured' ? 'bg-[#10B981]' : 'bg-[#142D4E]'
              }`}
            >
              GH
            </div>
            <div>
              <span className="font-semibold text-[#142D4E]">
                {githubStatus === 'configured'
                  ? activeSessionUser
                    ? `Connected as @${activeSessionUser}`
                    : 'GitHub Token Configured'
                  : 'Unauthenticated (Demo Mode)'}
              </span>
              <p className="text-[11px] text-[#74777F]">
                {githubStatus === 'configured'
                  ? 'Active backend authentication enabled with elevated 5,000 req/hr API rate limits.'
                  : 'Running with unauthenticated public rate limits (60 req/hr).'}
              </p>
            </div>
          </div>
          <span
            className={`px-2 py-0.5 rounded text-[11px] font-mono ${
              githubStatus === 'configured'
                ? 'bg-[#ECFDF5] text-[#047857] border border-[#A7F3D0]'
                : 'bg-[#E7F3FC] text-[#27609E]'
            }`}
          >
            {githubStatus === 'configured' ? 'Active' : 'Demo Mode'}
          </span>
        </div>
      </div>

      {/* Scan Boundaries */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#3269A8]" />
          <h3 className="text-xs font-semibold text-[#142D4E] uppercase tracking-wider font-mono">
            Scan Boundaries
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="flex flex-col gap-1">
            <label htmlFor="filesize" className="font-medium text-[#142D4E]">
              Max File Size for AST Parsing
            </label>
            <select
              id="filesize"
              value={maxFileSize}
              onChange={(e) => setMaxFileSize(e.target.value)}
              className="px-3 py-2 bg-[#F8FAFC] border border-[#8CC8F0]/60 rounded-lg text-xs text-[#142D4E] focus:outline-none focus:ring-1 focus:ring-[#8CC8F0]"
            >
              <option value="0.5">0.5 MB</option>
              <option value="1.0">1.0 MB (Default)</option>
              <option value="2.5">2.5 MB (Max limit)</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="branch-target" className="font-medium text-[#142D4E]">
              Branch Scope
            </label>
            <select
              id="branch-target"
              value={defaultBranch}
              onChange={(e) => setDefaultBranch(e.target.value)}
              className="px-3 py-2 bg-[#F8FAFC] border border-[#8CC8F0]/60 rounded-lg text-xs text-[#142D4E] focus:outline-none focus:ring-1 focus:ring-[#8CC8F0]"
            >
              <option value="default">Default branch (main / master)</option>
              <option value="all">All active branches</option>
            </select>
          </div>

          <div className="sm:col-span-2 flex flex-col gap-1.5 pt-1">
            <span className="font-medium text-[#142D4E]">Excluded Patterns</span>
            <div className="flex flex-wrap gap-1.5 font-mono text-[11px] text-[#44474E]">
              <span className="px-2 py-0.5 rounded bg-[#F8FAFC] border border-[#CBD5E1] flex items-center gap-1">
                <Folder className="w-3 h-3 text-[#74777F]" /> node_modules/
              </span>
              <span className="px-2 py-0.5 rounded bg-[#F8FAFC] border border-[#CBD5E1] flex items-center gap-1">
                <Folder className="w-3 h-3 text-[#74777F]" /> dist/
              </span>
              <span className="px-2 py-0.5 rounded bg-[#F8FAFC] border border-[#CBD5E1] flex items-center gap-1">
                <Folder className="w-3 h-3 text-[#74777F]" /> vendor/
              </span>
              <span className="px-2 py-0.5 rounded bg-[#F8FAFC] border border-[#CBD5E1]">
                *.min.js
              </span>
              <span className="px-2 py-0.5 rounded bg-[#FFDAD6] text-[#BA1A1A] border border-[#BA1A1A]/30 font-semibold">
                *.env*
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Automation */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col gap-3">
        <h3 className="text-xs font-semibold text-[#142D4E] uppercase tracking-wider font-mono">
          Automation
        </h3>

        <label className="p-3 bg-[#F8FAFC] rounded-lg border border-[#8CC8F0]/30 flex items-center justify-between gap-3 cursor-pointer">
          <div>
            <span className="text-xs font-semibold text-[#142D4E] block">
              Automatic Reassessment on Push
            </span>
            <p className="text-[11px] text-[#74777F] mt-0.5">
              Append a new evaluation snapshot when push events are received.
            </p>
          </div>
          <input
            type="checkbox"
            checked={autoReassess}
            onChange={(e) => setAutoReassess(e.target.checked)}
            className="w-4 h-4 rounded border-[#8CC8F0] text-[#3269A8] focus:ring-[#8CC8F0]"
          />
        </label>
      </div>
    </div>
  );
};
