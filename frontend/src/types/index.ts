/**
 * ProofPath AI - Core Domain Types
 * Based on ProofPath AI Detailed PRD v1.1
 */

export type AssessmentStatus =
  | 'demonstrated'
  | 'partially_demonstrated'
  | 'not_demonstrated_in_scope'
  | 'uncertain';

export interface RepositorySummary {
  name: string;
  url: string;
  description?: string;
  defaultBranch: string;
  lastCommitSha?: string;
  isEligible: boolean;
  skipReason?: string;
  language?: string;
  stars?: number;
}

export interface JobRequirement {
  id: string;
  skillName: string;
  category: 'core_required' | 'preferred_differentiator';
  description: string;
  provenance: 'fetched' | 'user_pasted';
  tags?: string[];
  sectionLabel?: string;
}

export interface SkillEvidenceItem {
  id: string;
  canonicalSkill: string;
  repositoryName: string;
  filePath: string;
  lineRange?: string;
  commitSha: string;
  explanation: string;
  limitations: string;
  astNodeType?: string;
  verifiedAt?: string;
}

export interface ScanStatusItem {
  repositoryName: string;
  commitSha: string;
  status: 'completed' | 'running' | 'queued' | 'partial' | 'failed';
  filesProcessed: number;
  totalFiles: number;
  skippedSummary?: string;
  startedAt?: string;
  durationMs?: number;
}

export interface WebhookDelivery {
  deliveryId: string;
  repositoryName: string;
  commitSha: string;
  eventType: string;
  changedPaths: string[];
  receivedAt: string;
  hmacVerified: boolean;
  reassessmentStatus: 'completed' | 'processing' | 'failed' | 'queued' | 'duplicate' | string;
  retryCount: number;
  reassessmentRunId?: string;
  errorDetails?: string;
}

export interface AssessmentSnapshot {
  id: string;
  snapshotNumber: number;
  timestamp: string;
  triggerType: 'initial_scan' | 'webhook_push' | 'manual_rescan';
  commitReferences: Record<string, string>;
  triggeringDeliveryId?: string;
  statusSummary: Record<AssessmentStatus, number>;
  statusTransitions?: Array<{
    skillName: string;
    previousStatus: AssessmentStatus;
    newStatus: AssessmentStatus;
    evidenceDelta: string;
  }>;
}

export const STATUS_CONFIG: Record<
  AssessmentStatus,
  {
    label: string;
    description: string;
    badgeBg: string;
    badgeText: string;
    borderColor: string;
    dotColor: string;
  }
> = {
  demonstrated: {
    label: 'Demonstrated',
    description: 'Scanned code provides direct, relevant support for the requirement.',
    badgeBg: 'bg-[#ECFDF5]',
    badgeText: 'text-[#047857]',
    borderColor: 'border-[#A7F3D0]',
    dotColor: 'bg-[#10B981]',
  },
  partially_demonstrated: {
    label: 'Partially Demonstrated',
    description: 'Some evidence exists, but it is incomplete, narrow, or missing important aspects.',
    badgeBg: 'bg-[#FFFBEB]',
    badgeText: 'text-[#B45309]',
    borderColor: 'border-[#FDE68A]',
    dotColor: 'bg-[#F59E0B]',
  },
  not_demonstrated_in_scope: {
    label: 'Not Demonstrated in Scope',
    description: 'The bounded scan did not find sufficient evidence. Note: This does NOT prove lack of skill.',
    badgeBg: 'bg-[#F1F5F9]',
    badgeText: 'text-[#475569]',
    borderColor: 'border-[#CBD5E1]',
    dotColor: 'bg-[#94A3B8]',
  },
  uncertain: {
    label: 'Uncertain',
    description: 'Evidence is ambiguous, inaccessible, conflicting, or insufficient for reliable classification.',
    badgeBg: 'bg-[#F3E8FF]',
    badgeText: 'text-[#7E22CE]',
    borderColor: 'border-[#D8B4FE]',
    dotColor: 'bg-[#A855F7]',
  },
};
