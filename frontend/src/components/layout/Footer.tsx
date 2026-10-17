import { Lock, FileCheck } from 'lucide-react';

export const Footer = () => {
  return (
    <footer className="w-full border-t border-[#8CC8F0]/30 bg-[#FFFFFF] py-6 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#44474E]">
        <div className="flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-[#3269A8]" />
          <span className="font-medium text-[#142D4E]">
            Product Principle:
          </span>
          <span className="italic">
            Show what the portfolio proves—and what it does not.
          </span>
        </div>

        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 font-mono text-[11px] bg-[#E7F3FC] px-2 py-0.5 rounded border border-[#8CC8F0]/40 text-[#27609E]">
            <Lock className="w-3 h-3 text-[#27609E]" />
            Read-only public metadata
          </span>
          <span className="font-mono text-[11px] text-[#44474E]/70">
            W-PS-2 · AI Career Coach
          </span>
        </div>
      </div>
    </footer>
  );
};
