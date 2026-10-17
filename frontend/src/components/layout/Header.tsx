import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { GitBranch, ShieldCheck, Settings, ChevronDown } from 'lucide-react';

export const Header = () => {
  const location = useLocation();
  const [navMenuOpen, setNavMenuOpen] = useState(false);
  const [demoGuideOpen, setDemoGuideOpen] = useState(false);

  const navLinks = [
    { label: '1. Portfolio', path: '/' },
    { label: '2. Repositories', path: '/repositories' },
    { label: '3. Target Job', path: '/jobs/new' },
    { label: '4. Requirements', path: '/jobs/review' },
    { label: '5. Scan Status', path: '/scans/status' },
    { label: '6. Skill Map', path: '/skills' },
    { label: '7. Gap Assessment', path: '/assessment' },
    { label: '8. Evidence', path: '/evidence' },
    { label: '9. Webhook', path: '/activity' },
    { label: '10. History', path: '/history' },
    { label: '11. Comparison', path: '/comparison' },
  ];

  const primarySteps = [
    { label: '1. Portfolio', path: '/', match: ['/', '/repositories'] },
    { label: '2. Target Job', path: '/jobs/new', match: ['/jobs/new', '/jobs/review'] },
    { label: '3. Assessment', path: '/assessment', match: ['/scans/status', '/skills', '/assessment', '/evidence'] },
    { label: '4. Webhooks & History', path: '/activity', match: ['/activity', '/history', '/comparison'] },
  ];

  const isStepActive = (matches: string[]) => {
    return matches.some((p) => (p === '/' ? location.pathname === '/' : location.pathname.startsWith(p)));
  };

  return (
    <header className="fixed top-0 w-full z-50 bg-[#FFFFFF] border-b border-[#8CC8F0]/30 shadow-[0_1px_2px_rgba(20,45,78,0.04)]">
      <div className="h-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        {/* Brand and Stage */}
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 hover:opacity-90 transition-opacity">
            <div className="w-8 h-8 rounded bg-[#142D4E] flex items-center justify-center text-white font-bold text-sm">
              <ShieldCheck className="w-5 h-5 text-[#8CC8F0]" />
            </div>
            <span className="font-semibold text-lg tracking-tight text-[#142D4E]">
              ProofPath AI
            </span>
          </Link>

          <div className="h-4 w-px bg-[#8CC8F0]/40 mx-1 hidden sm:block"></div>

          {/* Quick Screen Switcher Dropdown & Demo Mode Tag */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDemoGuideOpen(true)}
              className="inline-flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-[11px] font-mono px-2 sm:px-2.5 py-0.5 rounded-full bg-[#FFFBEB] hover:bg-[#FEF3C7] text-[#B45309] border border-[#FDE68A] font-medium transition-colors cursor-pointer select-none"
              title="Click for Demo & Transparency Guide"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]"></span>
              <span>Demo Mode</span>
              <span className="text-[9px] sm:text-[10px] text-[#B45309]/70 underline">Guide</span>
            </button>

            <div className="relative">
              <button
                onClick={() => setNavMenuOpen(!navMenuOpen)}
                className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-[#44474E] bg-[#E7F3FC] px-2.5 py-1 rounded-full border border-[#8CC8F0]/40 hover:bg-[#D7EAF8] transition-colors cursor-pointer"
              >
                <span className="text-[#3269A8] font-medium">Screens</span>
                <ChevronDown className="w-3.5 h-3.5 text-[#3269A8]" />
              </button>

            {navMenuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setNavMenuOpen(false)} />
                <div className="absolute left-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-[#8CC8F0]/40 py-2 z-50">
                  <div className="px-3 py-1 text-[11px] font-mono text-[#74777F] uppercase tracking-wider border-b border-[#8CC8F0]/20 mb-1">
                    PRD / Stitch Screens
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {navLinks.map((item, idx) => (
                      <Link
                        key={idx}
                        to={item.path}
                        onClick={() => setNavMenuOpen(false)}
                        className={`block px-3 py-1.5 text-xs font-sans hover:bg-[#E7F3FC] transition-colors ${
                          location.pathname === item.path
                            ? 'text-[#3269A8] font-semibold bg-[#E7F3FC]/50'
                            : 'text-[#142D4E]'
                        }`}
                      >
                        {item.label}
                      </Link>
                    ))}
                    <div className="border-t border-[#8CC8F0]/20 my-1 pt-1">
                      <Link
                        to="/settings"
                        onClick={() => setNavMenuOpen(false)}
                        className="block px-3 py-1.5 text-xs text-[#142D4E] hover:bg-[#E7F3FC]"
                      >
                        12. Settings & Integrations
                      </Link>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

        {/* Global Pipeline Steps */}
        <div className="flex items-center gap-4 sm:gap-6">
          <nav className="hidden md:flex items-center gap-6 text-sm">
            {primarySteps.map((step, idx) => {
              const active = isStepActive(step.match);
              return (
                <Link
                  key={idx}
                  to={step.path}
                  className={`transition-colors py-1 ${
                    active
                      ? 'font-medium text-[#142D4E] border-b-2 border-[#3269A8]'
                      : 'text-[#44474E]/70 hover:text-[#142D4E]'
                  }`}
                >
                  {step.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            <Link
              to="/settings"
              className={`p-1.5 rounded-lg border transition-colors ${
                location.pathname === '/settings'
                  ? 'bg-[#E7F3FC] text-[#3269A8] border-[#8CC8F0]'
                  : 'bg-white text-[#44474E] border-[#8CC8F0]/30 hover:bg-[#F8FAFC]'
              }`}
              title="Settings & Integrations"
            >
              <Settings className="w-4 h-4" />
            </Link>

            <Link
              to="/activity"
              className="w-8 h-8 rounded-full bg-[#142D4E] flex items-center justify-center text-white hover:bg-[#275488] transition-colors"
              title="GitHub Webhook Activity"
            >
              <GitBranch className="w-4 h-4 text-[#8CC8F0]" />
            </Link>
          </div>
        </div>
      </div>

      {/* Central Demo & Transparency Guide Modal */}
      {demoGuideOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#142D4E]/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-xl border border-[#8CC8F0]/50 max-w-lg w-full p-6 flex flex-col gap-4">
            <div className="flex items-center justify-between pb-2 border-b border-[#8CC8F0]/30">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#F59E0B]"></span>
                <h3 className="font-semibold text-base text-[#142D4E]">How This Demo Works</h3>
              </div>
              <button
                onClick={() => setDemoGuideOpen(false)}
                className="text-xs font-mono text-[#74777F] hover:text-[#142D4E] px-2 py-1 rounded bg-[#F8FAFC] border border-[#CBD5E1] cursor-pointer"
              >
                Close ✕
              </button>
            </div>

            <div className="flex flex-col gap-3 text-xs text-[#44474E] leading-relaxed">
              <div className="p-3 bg-[#ECFDF5] border border-[#A7F3D0] rounded-xl flex flex-col gap-1">
                <span className="font-semibold text-[#047857]">Active &amp; Functional in UI</span>
                <p>
                  All 12 routes, form validation, requirement addition, status filters, zero-state previews, and code inspectors are interactive.
                </p>
              </div>

              <div className="p-3 bg-[#FFFBEB] border border-[#FDE68A] rounded-xl flex flex-col gap-1">
                <span className="font-semibold text-[#B45309]">Sample Data Mode</span>
                <p>
                  Repositories, commit SHAs, AST nodes, and history snapshots are illustrative mocks so judges can test full evaluation without linking an external account.
                </p>
              </div>

              <div className="p-3 bg-[#E7F3FC] border border-[#8CC8F0]/40 rounded-xl flex flex-col gap-1">
                <span className="font-semibold text-[#3269A8]">Phase 3 Scope</span>
                <p>
                  Live GitHub REST API authentication, SSRF proxies, AST scanner workers, HMAC webhooks, and Supabase PostgreSQL persistence belong to Phase 3.
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={() => setDemoGuideOpen(false)}
                className="px-4 py-2 bg-[#142D4E] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
              >
                Got it, continue demo
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
