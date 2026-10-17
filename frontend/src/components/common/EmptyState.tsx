import type { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export const EmptyState = ({
  title,
  description,
  icon,
  action,
}: EmptyStateProps) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center bg-[#FFFFFF] border border-[#8CC8F0]/40 rounded-xl">
      <div className="w-12 h-12 rounded-full bg-[#E7F3FC] text-[#3269A8] flex items-center justify-center mb-4">
        {icon || <Inbox className="w-6 h-6" />}
      </div>
      <h3 className="text-base font-semibold text-[#142D4E] mb-1">{title}</h3>
      <p className="text-xs sm:text-sm text-[#44474E] max-w-md leading-relaxed mb-6">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};
