import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { EmptyState } from '../components/common/EmptyState';
import {
  Code,
  FolderGit2,
  ExternalLink,
  ArrowRight,
  Eye,
  EyeOff,
  Loader2,
} from 'lucide-react';
import { api, sessionStore } from '../api/client';

interface VerifiedSkillCard {
  id: string;
  category: string;
  name: string;
  repoCount: number;
  fileCount: number;
  primaryRepo: string;
  citations: Array<{
    filePath: string;
    description: string;
    url: string;
  }>;
}

export const PortfolioSkillMapPage = () => {
  const navigate = useNavigate();
  const portfolioId = sessionStore.getPortfolioId();

  const [isLoading, setIsLoading] = useState(false);
  const [showZeroState, setShowZeroState] = useState(false);
  const [skills, setSkills] = useState<VerifiedSkillCard[]>([]);

  useEffect(() => {
    async function loadEvidenceMap() {
      if (!portfolioId) {
        // Fallback demo state
        setSkills([
          {
            id: 'SKILL-01',
            category: 'BACKEND ARCHITECTURE',
            name: 'TypeScript & Node.js Backend Microservices',
            repoCount: 2,
            fileCount: 18,
            primaryRepo: 'core-ledger-service',
            citations: [
              {
                filePath: 'src/services/auth-handler.ts',
                description: 'JWT verification and route authentication middleware',
                url: '#',
              },
            ],
          },
          {
            id: 'SKILL-02',
            category: 'DATA PERSISTENCE',
            name: 'PostgreSQL Relational Schema & Migrations',
            repoCount: 1,
            fileCount: 7,
            primaryRepo: 'core-ledger-service',
            citations: [
              {
                filePath: 'prisma/schema.prisma',
                description: 'Relational schema model with foreign keys and indexes',
                url: '#',
              },
            ],
          },
          {
            id: 'SKILL-03',
            category: 'INFRASTRUCTURE / DEVOPS',
            name: 'Docker Multi-Stage Builds & CI/CD Pipelines',
            repoCount: 2,
            fileCount: 4,
            primaryRepo: 'telemetry-agent',
            citations: [
              {
                filePath: 'Dockerfile',
                description: 'Multi-stage container build with security hardening',
                url: '#',
              },
            ],
          },
        ]);
        return;
      }

      setIsLoading(true);
      try {
        const res = await api.getEvidence(portfolioId);
        if (res.evidence.length === 0) {
          setShowZeroState(true);
          setSkills([]);
          return;
        }

        // Group evidence items by canonical_skill
        const bySkill: Record<string, typeof res.evidence> = {};
        res.evidence.forEach((ev) => {
          const s = ev.canonical_skill;
          if (!bySkill[s]) bySkill[s] = [];
          bySkill[s].push(ev);
        });

        const cards: VerifiedSkillCard[] = Object.entries(bySkill).map(([skillName, items], idx) => {
          const repos = new Set(items.map((i) => i.repository_name || i.repository_id));
          const files = new Set(items.map((i) => i.file_path));
          const primaryRepo = items[0]?.repository_name || 'repository';

          return {
            id: `SKILL-${String(idx + 1).padStart(2, '0')}`,
            category: 'VERIFIED CODE EVIDENCE',
            name: skillName,
            repoCount: repos.size,
            fileCount: files.size,
            primaryRepo,
            citations: items.slice(0, 3).map((item) => ({
              filePath: `${item.file_path} (${item.line_range || 'code'})`,
              description: item.explanation,
              url: `/evidence?file=${encodeURIComponent(item.file_path)}&lines=${encodeURIComponent(item.line_range || '')}`,
            })),
          };
        });

        setSkills(cards);
      } catch (err) {
        console.warn('Error loading skill map:', err);
      } finally {
        setIsLoading(false);
      }
    }

    loadEvidenceMap();
  }, [portfolioId]);

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Your Skill Map"
        description="Skills identified in your scanned code."
        badge={portfolioId ? "Persisted Code Evidence" : "Sample Demo"}
        breadcrumbs={[
          { label: 'Repositories', to: '/repositories' },
          { label: 'Scan', to: '/scans/status' },
          { label: 'Skill Map' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowZeroState(!showZeroState)}
              className="px-2.5 py-1.5 rounded-lg border border-[#8CC8F0]/40 text-xs font-mono text-[#44474E] hover:bg-[#F8FAFC] transition-colors flex items-center gap-1 cursor-pointer"
            >
              {showZeroState ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              <span>{showZeroState ? 'Show Evidence' : 'Preview Empty'}</span>
            </button>

            <button
              onClick={() => navigate('/assessment')}
              className="px-4 py-1.5 rounded-lg bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
            >
              <span>Evaluate Against Job</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        }
      />

      {isLoading && (
        <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 text-[#3269A8] animate-spin" />
          <span className="text-xs text-[#44474E]">Aggregating ground-truth skill evidence...</span>
        </div>
      )}

      {/* ZERO STATE PREVIEW */}
      {!isLoading && (showZeroState || skills.length === 0) ? (
        <EmptyState
          icon={<Code className="w-6 h-6" />}
          title="No verified evidence extracted yet"
          description="We haven't detected code citations in your selected repositories yet. Try rescanning or adding repositories with supported languages."
          action={
            <button
              onClick={() => navigate('/repositories')}
              className="px-4 py-2 bg-[#3269A8] hover:bg-[#275488] text-white text-xs font-semibold rounded-lg"
            >
              Select Repositories
            </button>
          }
        />
      ) : (
        /* SKILL CARDS GRID */
        !isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {skills.map((skill) => (
              <div
                key={skill.id}
                className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col justify-between gap-4"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] tracking-wider text-[#3269A8] font-bold">
                      {skill.category}
                    </span>
                    <span className="font-mono text-xs text-[#74777F]">{skill.id}</span>
                  </div>

                  <h3 className="font-semibold text-sm text-[#142D4E]">{skill.name}</h3>

                  <div className="flex items-center gap-3 text-xs text-[#74777F] font-mono pt-1">
                    <span className="flex items-center gap-1">
                      <FolderGit2 className="w-3.5 h-3.5 text-[#3269A8]" />
                      {skill.repoCount} {skill.repoCount === 1 ? 'repo' : 'repos'}
                    </span>
                    <span>{skill.fileCount} {skill.fileCount === 1 ? 'file' : 'files'}</span>
                    <span className="truncate">Primary: {skill.primaryRepo}</span>
                  </div>
                </div>

                {/* Evidence citations */}
                <div className="border-t border-[#8CC8F0]/20 pt-3 flex flex-col gap-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-[#74777F] font-semibold">
                    Sample Citations
                  </span>
                  <div className="flex flex-col gap-1.5">
                    {skill.citations.map((c, idx) => (
                      <Link
                        key={idx}
                        to={c.url}
                        className="text-xs flex items-center justify-between gap-2 p-1.5 rounded hover:bg-[#F8FAFC] transition-colors group"
                      >
                        <span className="font-mono text-[#3269A8] truncate flex-1 group-hover:underline">
                          {c.filePath}
                        </span>
                        <ExternalLink className="w-3 h-3 text-[#74777F] shrink-0" />
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
};
