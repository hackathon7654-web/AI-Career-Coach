import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  FileCode,
  GitCommit,
  Loader2,
} from 'lucide-react';
import { api, sessionStore } from '../api/client';

export const EvidenceDetailsPage = () => {
  const [searchParams] = useSearchParams();
  const fileParam = searchParams.get('file') || 'src/services/auth-handler.ts';
  const repoParam = searchParams.get('repo') || 'core-ledger-service';
  const linesParam = searchParams.get('lines') || 'L24-L58';
  const portfolioId = sessionStore.getPortfolioId();

  const [isLoading, setIsLoading] = useState(false);
  const [commitSha, setCommitSha] = useState('7f2d8a4');
  const [astNodeType, setAstNodeType] = useState('ClassDeclaration');
  const [canonicalSkill, setCanonicalSkill] = useState('TypeScript Backend');
  const [explanation, setExplanation] = useState('AuthHandler token verification middleware');
  const [snippet, setSnippet] = useState<string>(`import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

export interface AuthenticatedUser {
  userId: string;
  roles: string[];
}

export class AuthHandler {
  private readonly secretKey: string;

  constructor(secretKey: string) {
    this.secretKey = secretKey;
  }

  public verifyToken(req: Request, res: Response, next: NextFunction): void {
    const authHeader = req.headers.authorization;
    if (!authHeader?.startsWith('Bearer ')) {
      res.status(401).json({ error: 'Missing or malformed Authorization header' });
      return;
    }

    const token = authHeader.substring(7);
    try {
      const decoded = jwt.verify(token, this.secretKey) as AuthenticatedUser;
      (req as any).user = decoded;
      next();
    } catch (err) {
      res.status(403).json({ error: 'Cryptographic signature validation failed' });
    }
  }
}`);

  useEffect(() => {
    async function loadRealEvidence() {
      if (!portfolioId) return;
      setIsLoading(true);
      try {
        const res = await api.getEvidence(portfolioId);
        const match = res.evidence.find(
          (e) => e.file_path === fileParam || e.line_range === linesParam
        );
        if (match) {
          setCommitSha(match.commit_sha.slice(0, 7));
          setAstNodeType(match.ast_node_type || match.evidence_type);
          setCanonicalSkill(match.canonical_skill);
          setExplanation(match.explanation);
          if (match.snippet) {
            setSnippet(match.snippet);
          }
        }
      } catch (err) {
        console.warn('Error loading evidence item:', err);
      } finally {
        setIsLoading(false);
      }
    }

    loadRealEvidence();
  }, [portfolioId, fileParam, linesParam]);

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Code Evidence"
        description="Line-by-line inspection for demonstrated skills."
        badge={portfolioId ? "Ground-Truth Citation" : "Sample Demo"}
        backLink={{ label: 'Back to Assessment', to: '/assessment' }}
        breadcrumbs={[
          { label: 'Assessment', to: '/assessment' },
          { label: 'Code Evidence' },
        ]}
      />

      {/* Evidence Summary Card */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-5 shadow-xs flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-[#3269A8] font-semibold">
              {canonicalSkill}
            </span>
            <h2 className="text-base font-semibold text-[#142D4E] mt-0.5">
              {explanation}
            </h2>
          </div>
          <StatusBadge status="demonstrated" size="sm" />
        </div>

        {/* Metadata Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-[#8CC8F0]/20 font-mono text-xs">
          <div>
            <span className="text-[#74777F] block text-[11px]">Repository</span>
            <span className="font-medium text-[#142D4E]">{repoParam}</span>
          </div>
          <div>
            <span className="text-[#74777F] block text-[11px]">Commit</span>
            <span className="font-medium text-[#3269A8] flex items-center gap-1">
              <GitCommit className="w-3.5 h-3.5" /> {commitSha}
            </span>
          </div>
          <div>
            <span className="text-[#74777F] block text-[11px]">Lines</span>
            <span className="font-medium text-[#142D4E]">{linesParam}</span>
          </div>
          <div>
            <span className="text-[#74777F] block text-[11px]">Syntax Node</span>
            <span className="font-medium text-[#047857]">{astNodeType}</span>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 text-[#3269A8] animate-spin" />
          <span className="text-xs text-[#44474E]">Loading evidence details...</span>
        </div>
      )}

      {/* Code Snippet Viewer */}
      {!isLoading && (
        <div className="bg-[#142D4E] text-[#F8FAFC] rounded-xl overflow-hidden border border-[#8CC8F0]/40 shadow-xs flex flex-col">
          <div className="px-4 py-2.5 bg-[#001835] border-b border-[#8CC8F0]/20 flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2">
              <FileCode className="w-4 h-4 text-[#8CC8F0]" />
              <span className="text-white font-medium">{fileParam}</span>
              <span className="text-[#8CC8F0]/60">•</span>
              <span className="text-[#8CC8F0]">{linesParam}</span>
            </div>

            <span className="text-[11px] font-mono text-[#8CC8F0]">SHA: {commitSha}</span>
          </div>

          <div className="p-4 overflow-x-auto text-xs font-mono leading-relaxed">
            <pre className="text-[#E7F3FC]">{snippet}</pre>
          </div>

          <div className="px-4 py-2 bg-[#001835]/70 border-t border-[#8CC8F0]/20 text-[11px] font-mono text-[#8CC8F0]/80">
            Ground-truth code citation from {repoParam} ({linesParam})
          </div>
        </div>
      )}
    </div>
  );
};
