import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface ScreenHeaderProps {
  title: string;
  description?: string;
  badge?: string;
  breadcrumbs?: BreadcrumbItem[];
  backLink?: { label: string; to: string };
  actions?: ReactNode;
}

export const ScreenHeader = ({
  title,
  description,
  badge,
  breadcrumbs,
  backLink,
  actions,
}: ScreenHeaderProps) => {
  return (
    <div className="flex flex-col gap-2.5 sm:gap-3 pb-4 sm:pb-6 border-b border-[#8CC8F0]/30 mb-5 sm:mb-6">
      {/* Back link or Breadcrumbs */}
      {(backLink || breadcrumbs) && (
        <div className="flex items-center gap-2 text-xs font-mono text-[#44474E] flex-wrap">
          {backLink && (
            <Link
              to={backLink.to}
              className="inline-flex items-center gap-1 text-[#3269A8] hover:underline font-sans text-xs font-medium mr-2"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>{backLink.label}</span>
            </Link>
          )}

          {breadcrumbs &&
            breadcrumbs.map((crumb, idx) => (
              <span key={idx} className="flex items-center gap-2">
                {idx > 0 && <span className="text-[#74777F] select-none">/</span>}
                {crumb.to ? (
                  <Link to={crumb.to} className="hover:text-[#3269A8] transition-colors">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-[#142D4E] font-medium">{crumb.label}</span>
                )}
              </span>
            ))}
        </div>
      )}

      {/* Title & Actions Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
        <div className="flex flex-col gap-1 max-w-3xl">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold tracking-tight text-[#142D4E]">
              {title}
            </h1>
            {badge && (
              <span className="px-2 py-0.5 rounded font-mono text-xs bg-[#E7F3FC] text-[#27609E] border border-[#8CC8F0]/40 font-medium">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs sm:text-sm text-[#44474E] leading-relaxed">
              {description}
            </p>
          )}
        </div>

        {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};
