import { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp, Database, Cpu } from 'lucide-react';

interface DemoModeBannerProps {
  screenName: string;
  dataType?: 'sample_data' | 'local_interaction' | 'disconnected_backend';
  customNote?: string;
}

export const DemoModeBanner = ({
  screenName,
  dataType: _dataType = 'sample_data',
  customNote,
}: DemoModeBannerProps) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <aside 
      aria-label="Demo mode disclosure"
      className="w-full bg-[#E7F3FC]/70 border border-[#8CC8F0]/60 rounded-xl p-3.5 mb-2 text-xs transition-all"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-[#3269A8] text-white uppercase tracking-wider flex items-center gap-1 shadow-xs">
            <Cpu className="w-3 h-3" />
            Demo Mode — Illustrative Scenario
          </span>

          <span className="text-[#142D4E] font-medium">
            {customNote || `Displaying sample data for ${screenName} review.`}
          </span>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="inline-flex items-center gap-1 text-[11px] font-mono text-[#27609E] hover:text-[#142D4E] self-start sm:self-auto cursor-pointer"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          <span>{expanded ? 'Hide Jury Guide' : 'Jury & Transparency Guide'}</span>
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-[#8CC8F0]/40 grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] text-[#44474E] leading-relaxed">
          <div className="p-2.5 bg-white/80 rounded-lg border border-[#8CC8F0]/30 flex flex-col gap-1">
            <span className="font-semibold text-[#047857] flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#10B981]"></span>
              Active &amp; Functional in UI
            </span>
            <p>
              Navigation, route hierarchy, input validation, inclusion filters, custom requirement forms, and the 4 PRD assessment states operate live locally.
            </p>
          </div>

          <div className="p-2.5 bg-white/80 rounded-lg border border-[#8CC8F0]/30 flex flex-col gap-1">
            <span className="font-semibold text-[#B45309] flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#F59E0B]"></span>
              Illustrative Sample Content
            </span>
            <p>
              Repositories, commit SHAs, AST parsing snippets, and past snapshots are representative mocks so you can test full workflow evaluation without linking an external account.
            </p>
          </div>

          <div className="p-2.5 bg-white/80 rounded-lg border border-[#8CC8F0]/30 flex flex-col gap-1">
            <span className="font-semibold text-[#3269A8] flex items-center gap-1">
              <Database className="w-3 h-3 text-[#3269A8]" />
              Phase 3 Implementation Scope
            </span>
            <p>
              Live GitHub API authentication, server-side SSRF network proxies, tree-sitter AST extraction, HMAC-SHA256 webhook ingestion, and Supabase PostgreSQL persistence are scheduled for Phase 3.
            </p>
          </div>
        </div>
      )}
    </aside>
  );
};
