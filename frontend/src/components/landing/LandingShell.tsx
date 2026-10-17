import { useState, type FormEvent } from 'react';
import { Search, ShieldAlert, GitCommit, CheckCircle2, Layers } from 'lucide-react';

export const LandingShell = () => {
  const [profileInput, setProfileInput] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-8 py-4">
      {/* Hero / Identity Section */}
      <div className="flex flex-col gap-3">
        <div className="inline-flex items-center gap-2 self-start px-3 py-1 rounded-full bg-[#E7F3FC] border border-[#8CC8F0]/50 text-xs font-mono text-[#27609E]">
          <span className="w-2 h-2 rounded-full bg-[#3269A8] animate-pulse"></span>
          <span>Phase 1: Frontend Foundation Active</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-[#142D4E]">
          Connect your GitHub portfolio
        </h1>
        <p className="text-base sm:text-lg text-[#44474E] max-w-2xl leading-relaxed">
          ProofPath AI compares target job requirements against verifiable code evidence across your accessible public repositories. It traces demonstrated skills to exact commit SHAs and file paths.
        </p>
      </div>

      {/* Main Intake Form Shell (Matching Stitch Screen 1) */}
      <div className="bg-[#FFFFFF] border border-[#8CC8F0]/40 rounded-xl p-6 sm:p-8 shadow-sm flex flex-col gap-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
            <label htmlFor="github-handle" className="text-base font-medium text-[#142D4E]">
              GitHub profile URL or username
            </label>
            <span className="font-mono text-xs text-[#44474E] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#8CC8F0]/30">
              Public metadata only · No private tokens required
            </span>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch gap-3">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#74777F]">
                <svg className="w-5 h-5 text-[#74777F]" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
              </div>
              <input
                id="github-handle"
                type="text"
                value={profileInput}
                onChange={(e) => setProfileInput(e.target.value)}
                placeholder="e.g., https://github.com/username or octocat"
                className="w-full pl-11 pr-4 py-2.5 bg-[#F8FAFC] border border-[#8CC8F0]/60 text-[#142D4E] rounded-lg font-sans text-sm focus:outline-none focus:bg-[#FFFFFF] focus:ring-2 focus:ring-[#8CC8F0] placeholder:text-[#74777F]"
                spellCheck={false}
              />
            </div>
            <button
              type="submit"
              className="px-5 py-2.5 bg-[#3269A8] hover:bg-[#275488] active:bg-[#1D3F66] text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center gap-2 shadow-sm cursor-pointer whitespace-nowrap"
            >
              <Search className="w-4 h-4" />
              <span>Find Repositories</span>
            </button>
          </div>
        </form>

        {/* 4-Step Pipeline Indicator */}
        <div className="pt-4 border-t border-[#8CC8F0]/20 grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#E7F3FC]/50 border border-[#8CC8F0]/40">
            <span className="font-mono text-xs font-bold text-[#3269A8] bg-[#FFFFFF] w-6 h-6 rounded flex items-center justify-center border border-[#8CC8F0]/50 shrink-0">
              01
            </span>
            <div>
              <p className="text-xs font-semibold text-[#142D4E]">Profile Intake</p>
              <p className="text-[11px] text-[#44474E] mt-0.5">Public repo discovery</p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/20">
            <span className="font-mono text-xs font-bold text-[#74777F] bg-[#FFFFFF] w-6 h-6 rounded flex items-center justify-center border border-[#8CC8F0]/30 shrink-0">
              02
            </span>
            <div>
              <p className="text-xs font-medium text-[#142D4E]">Scope Selection</p>
              <p className="text-[11px] text-[#44474E] mt-0.5">Bounded file scanning</p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/20">
            <span className="font-mono text-xs font-bold text-[#74777F] bg-[#FFFFFF] w-6 h-6 rounded flex items-center justify-center border border-[#8CC8F0]/30 shrink-0">
              03
            </span>
            <div>
              <p className="text-xs font-medium text-[#142D4E]">Job Extraction</p>
              <p className="text-[11px] text-[#44474E] mt-0.5">Core & preferred skills</p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/20">
            <span className="font-mono text-xs font-bold text-[#74777F] bg-[#FFFFFF] w-6 h-6 rounded flex items-center justify-center border border-[#8CC8F0]/30 shrink-0">
              04
            </span>
            <div>
              <p className="text-xs font-medium text-[#142D4E]">Evidence Assessment</p>
              <p className="text-[11px] text-[#44474E] mt-0.5">Reassessment loop</p>
            </div>
          </div>
        </div>
      </div>

      {/* Safety & Grounding Constraints Card */}
      <div className="bg-[#FFFFFF] border border-[#8CC8F0]/30 rounded-xl p-6 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-[#142D4E]">
          <ShieldAlert className="w-5 h-5 text-[#3269A8]" />
          <h2 className="text-base font-semibold">
            Bounded Scan & Integrity Rules (PRD Compliance)
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-[#44474E]">
          <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/20 flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 font-medium text-[#142D4E]">
              <GitCommit className="w-3.5 h-3.5 text-[#3269A8]" />
              <span>SHA-Pinned Evidence</span>
            </div>
            <p>
              Every demonstrated skill points to an exact commit SHA and file path. Evidence is never invented or hallucinated.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/20 flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 font-medium text-[#142D4E]">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#3269A8]" />
              <span>Secret & Binary Exclusion</span>
            </div>
            <p>
              Scanners strictly exclude <code className="bg-[#E7F3FC] px-1 py-0.2 rounded font-mono text-[11px]">.env</code> files, credentials, private keys, and binary blobs before analysis.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#8CC8F0]/20 flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 font-medium text-[#142D4E]">
              <Layers className="w-3.5 h-3.5 text-[#3269A8]" />
              <span>Explainable Gap Statuses</span>
            </div>
            <p>
              Requirements are strictly classified as <em className="font-semibold text-[#142D4E]">demonstrated</em>, <em className="font-semibold text-[#142D4E]">partially_demonstrated</em>, <em className="font-semibold text-[#142D4E]">not_demonstrated_in_scope</em>, or <em className="font-semibold text-[#142D4E]">uncertain</em>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
