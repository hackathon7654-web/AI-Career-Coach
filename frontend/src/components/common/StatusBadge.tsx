import { STATUS_CONFIG, type AssessmentStatus } from '../../types';

interface StatusBadgeProps {
  status: AssessmentStatus;
  size?: 'sm' | 'md';
}

export const StatusBadge = ({ status, size = 'md' }: StatusBadgeProps) => {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.uncertain;

  const sizeClasses =
    size === 'sm'
      ? 'px-2 py-0.5 text-[11px] gap-1'
      : 'px-2.5 py-1 text-xs gap-1.5';

  return (
    <span
      className={`inline-flex items-center rounded-full font-mono font-medium border ${config.badgeBg} ${config.badgeText} ${config.borderColor} ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${config.dotColor}`} />
      <span>{config.label}</span>
    </span>
  );
};
