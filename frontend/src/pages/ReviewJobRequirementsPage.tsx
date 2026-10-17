import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../components/common/ScreenHeader';
import {
  CheckSquare,
  PlusCircle,
  ArrowRight,
  Sliders,
  Loader2,
  Trash2,
} from 'lucide-react';
import type { JobRequirement } from '../types';
import { api, sessionStore } from '../api/client';

export const ReviewJobRequirementsPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const jobId = searchParams.get('job_id') || sessionStore.getJobId();

  const [jobTitle, setJobTitle] = useState('Target Job');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const [coreRequirements, setCoreRequirements] = useState<JobRequirement[]>([]);
  const [preferredRequirements, setPreferredRequirements] = useState<JobRequirement[]>([]);
  const [includedIds, setIncludedIds] = useState<Record<string, boolean>>({});

  const [newSkillName, setNewSkillName] = useState('');
  const [newCategory, setNewCategory] = useState<'core_required' | 'preferred_differentiator'>('core_required');

  useEffect(() => {
    async function fetchJobData() {
      if (!jobId) {
        // Fallback default sample data if accessed directly without job ID
        const defaultCore: JobRequirement[] = [
          {
            id: 'req_01',
            skillName: 'Go or TypeScript for Distributed Backend Services',
            category: 'core_required',
            description: 'High-throughput backend services, goroutines/async concurrency, and error handling.',
            provenance: 'user_pasted',
            tags: ['TypeScript', 'Go', 'Concurrency'],
            sectionLabel: 'Required Skills',
          },
          {
            id: 'req_02',
            skillName: 'Event-Driven Architecture & Message Queues',
            category: 'core_required',
            description: 'Consumer/publisher services with RabbitMQ, Apache Kafka, or SQS.',
            provenance: 'user_pasted',
            tags: ['Kafka', 'RabbitMQ', 'Async'],
            sectionLabel: 'Required Skills',
          },
          {
            id: 'req_03',
            skillName: 'PostgreSQL Database Design & SQL Migrations',
            category: 'core_required',
            description: 'Relational modeling, indexing, and transactional DDL migration scripts.',
            provenance: 'user_pasted',
            tags: ['PostgreSQL', 'SQL Migrations'],
            sectionLabel: 'Required Skills',
          },
          {
            id: 'req_04',
            skillName: 'Docker Containerization & CI/CD Pipelines',
            category: 'core_required',
            description: 'Multi-stage Dockerfiles and automated GitHub Actions workflows.',
            provenance: 'user_pasted',
            tags: ['Docker', 'CI/CD'],
            sectionLabel: 'Required Skills',
          },
        ];
        const defaultPref: JobRequirement[] = [
          {
            id: 'pref_01',
            skillName: 'Kubernetes Operator Development & Custom CRDs',
            category: 'preferred_differentiator',
            description: 'Custom Resource Definitions with reconciliation controllers.',
            provenance: 'user_pasted',
            tags: ['Kubernetes', 'CRDs'],
            sectionLabel: 'Preferred Skills',
          },
          {
            id: 'pref_02',
            skillName: 'OpenTelemetry Distributed Tracing & Metrics',
            category: 'preferred_differentiator',
            description: 'Context propagation across services and metric collectors.',
            provenance: 'user_pasted',
            tags: ['OpenTelemetry', 'Tracing'],
            sectionLabel: 'Preferred Skills',
          },
        ];
        setCoreRequirements(defaultCore);
        setPreferredRequirements(defaultPref);
        const inc: Record<string, boolean> = {};
        [...defaultCore, ...defaultPref].forEach((r) => (inc[r.id] = true));
        setIncludedIds(inc);
        return;
      }

      setIsLoading(true);
      try {
        const job = await api.getJob(jobId);
        setJobTitle(job.title || 'Target Job');
        const core: JobRequirement[] = [];
        const pref: JobRequirement[] = [];
        const inc: Record<string, boolean> = {};

        (job.requirements || []).forEach((r: any) => {
          const reqItem: JobRequirement = {
            id: r.id,
            skillName: r.skill_name,
            category: r.category,
            description: r.description || '',
            provenance: r.provenance || 'user_pasted',
            tags: r.tags || [],
            sectionLabel: r.section_label || (r.category === 'core_required' ? 'Required Skills' : 'Preferred Skills'),
          };
          if (r.category === 'core_required') {
            core.push(reqItem);
          } else {
            pref.push(reqItem);
          }
          inc[r.id] = r.is_included !== false;
        });

        setCoreRequirements(core);
        setPreferredRequirements(pref);
        setIncludedIds(inc);
      } catch (err: any) {
        setErrorMessage(err.message || 'Failed to load job requirements.');
      } finally {
        setIsLoading(false);
      }
    }

    fetchJobData();
  }, [jobId]);

  const toggleRequirement = (id: string) => {
    setIncludedIds((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleDeleteRequirement = (id: string, category: 'core_required' | 'preferred_differentiator') => {
    if (category === 'core_required') {
      setCoreRequirements((prev) => prev.filter((r) => r.id !== id));
    } else {
      setPreferredRequirements((prev) => prev.filter((r) => r.id !== id));
    }
    setIncludedIds((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
  };

  const handleAddCustomRequirement = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSkillName.trim()) return;

    const newId = `custom_${Date.now().toString().slice(-4)}`;
    const newReq: JobRequirement = {
      id: newId,
      skillName: newSkillName.trim(),
      category: newCategory,
      description: 'Candidate added custom skill requirement',
      provenance: 'user_pasted',
      tags: [newSkillName.trim()],
      sectionLabel: newCategory === 'core_required' ? 'Required Skills' : 'Preferred Skills',
    };

    if (newCategory === 'core_required') {
      setCoreRequirements((prev) => [...prev, newReq]);
    } else {
      setPreferredRequirements((prev) => [...prev, newReq]);
    }

    setIncludedIds((prev) => ({ ...prev, [newId]: true }));
    setNewSkillName('');
  };

  const totalActive = Object.values(includedIds).filter(Boolean).length;

  const handleProceed = async () => {
    if (jobId) {
      setIsSaving(true);
      try {
        const allReqs = [...coreRequirements, ...preferredRequirements].map((r) => ({
          id: r.id,
          skill_name: r.skillName,
          category: r.category,
          description: r.description,
          provenance: r.provenance,
          tags: r.tags || [],
          section_label: r.sectionLabel,
          is_included: !!includedIds[r.id],
          is_candidate_edited: true,
        }));
        await api.updateJobRequirements(jobId, allReqs);
      } catch (err: any) {
        console.warn('Saving requirements error non-blocking:', err);
      } finally {
        setIsSaving(false);
      }
    }

    navigate('/scans/status');
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      <ScreenHeader
        title="Review Job Skills"
        description="Select skills to evaluate against your code."
        badge={jobTitle}
        breadcrumbs={[
          { label: 'Target Job', to: '/jobs/new' },
          { label: 'Review Skills' },
        ]}
        actions={
          <button
            onClick={handleProceed}
            disabled={totalActive === 0 || isSaving}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold text-white transition-colors flex items-center gap-1.5 shadow-xs ${
              totalActive > 0 && !isSaving
                ? 'bg-[#3269A8] hover:bg-[#275488] cursor-pointer'
                : 'bg-[#74777F] opacity-50 cursor-not-allowed'
            }`}
          >
            {isSaving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <span>Start Assessment ({totalActive})</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        }
      />

      {isLoading && (
        <div className="p-8 bg-white border border-[#8CC8F0]/30 rounded-xl flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 text-[#3269A8] animate-spin" />
          <span className="text-xs text-[#44474E]">Loading extracted job skills...</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3.5 bg-[#FEE2E2] border border-[#FCA5A5] rounded-xl text-xs text-[#991B1B]">
          {errorMessage}
        </div>
      )}

      {/* REQUIRED SKILLS */}
      {!isLoading && (
        <div className="bg-white border border-[#8CC8F0]/40 rounded-xl overflow-hidden shadow-xs flex flex-col">
          <div className="p-3.5 bg-[#F8FAFC] border-b border-[#8CC8F0]/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-[#3269A8]" />
              <h2 className="font-semibold text-xs sm:text-sm text-[#142D4E]">
                Required Core Skills
              </h2>
            </div>
            <span className="font-mono text-xs text-[#44474E]">
              {coreRequirements.filter((r) => includedIds[r.id]).length} of {coreRequirements.length} active
            </span>
          </div>

          <div className="divide-y divide-[#8CC8F0]/20">
            {coreRequirements.map((req) => {
              const isChecked = !!includedIds[req.id];
              return (
                <div
                  key={req.id}
                  className={`p-3.5 flex items-start gap-3 transition-colors ${
                    isChecked ? 'bg-white' : 'bg-[#F8FAFC] opacity-60'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleRequirement(req.id)}
                    className="mt-0.5 rounded border-[#8CC8F0] text-[#3269A8] focus:ring-[#8CC8F0] cursor-pointer"
                  />
                  <div className="flex flex-col gap-1 flex-1">
                    <span className="font-medium text-xs sm:text-sm text-[#142D4E]">
                      {req.skillName}
                    </span>
                    {req.description && (
                      <p className="text-xs text-[#44474E] leading-relaxed">
                        {req.description}
                      </p>
                    )}
                    {req.tags && req.tags.length > 0 && (
                      <div className="flex items-center gap-1.5 pt-0.5 flex-wrap">
                        {req.tags.map((t) => (
                          <span
                            key={t}
                            className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#E7F3FC] text-[#27609E]"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteRequirement(req.id, 'core_required')}
                    className="text-[#74777F] hover:text-[#BA1A1A] p-1 transition-colors"
                    title="Remove skill"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* PREFERRED / DIFFERENTIATOR SKILLS */}
      {!isLoading && (
        <div className="bg-white border border-[#8CC8F0]/40 rounded-xl overflow-hidden shadow-xs flex flex-col">
          <div className="p-3.5 bg-[#F8FAFC] border-b border-[#8CC8F0]/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-[#D97706]" />
              <h2 className="font-semibold text-xs sm:text-sm text-[#142D4E]">
                Preferred Skills & Differentiators
              </h2>
            </div>
            <span className="font-mono text-xs text-[#44474E]">
              {preferredRequirements.filter((r) => includedIds[r.id]).length} of {preferredRequirements.length} active
            </span>
          </div>

          <div className="divide-y divide-[#8CC8F0]/20">
            {preferredRequirements.map((req) => {
              const isChecked = !!includedIds[req.id];
              return (
                <div
                  key={req.id}
                  className={`p-3.5 flex items-start gap-3 transition-colors ${
                    isChecked ? 'bg-white' : 'bg-[#F8FAFC] opacity-60'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleRequirement(req.id)}
                    className="mt-0.5 rounded border-[#8CC8F0] text-[#3269A8] focus:ring-[#8CC8F0] cursor-pointer"
                  />
                  <div className="flex flex-col gap-1 flex-1">
                    <span className="font-medium text-xs sm:text-sm text-[#142D4E]">
                      {req.skillName}
                    </span>
                    {req.description && (
                      <p className="text-xs text-[#44474E] leading-relaxed">
                        {req.description}
                      </p>
                    )}
                    {req.tags && req.tags.length > 0 && (
                      <div className="flex items-center gap-1.5 pt-0.5 flex-wrap">
                        {req.tags.map((t) => (
                          <span
                            key={t}
                            className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#FEF3C7] text-[#92400E]"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteRequirement(req.id, 'preferred_differentiator')}
                    className="text-[#74777F] hover:text-[#BA1A1A] p-1 transition-colors"
                    title="Remove skill"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ADD CUSTOM SKILL */}
      <div className="bg-white border border-[#8CC8F0]/40 rounded-xl p-4 shadow-xs">
        <form onSubmit={handleAddCustomRequirement} className="flex flex-col sm:flex-row items-center gap-2.5">
          <input
            type="text"
            value={newSkillName}
            onChange={(e) => setNewSkillName(e.target.value)}
            placeholder="Add custom required or differentiator skill..."
            className="flex-1 px-3 py-2 bg-[#F8FAFC] border border-[#8CC8F0]/60 text-[#142D4E] rounded-lg text-xs sm:text-sm focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#8CC8F0] placeholder:text-[#74777F]"
          />
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value as any)}
            className="px-3 py-2 bg-[#F8FAFC] border border-[#8CC8F0]/60 text-[#142D4E] rounded-lg text-xs font-mono focus:outline-none"
          >
            <option value="core_required">Core Required</option>
            <option value="preferred_differentiator">Preferred</option>
          </select>
          <button
            type="submit"
            disabled={!newSkillName.trim()}
            className="px-4 py-2 bg-[#142D4E] hover:bg-[#1D3F66] disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>Add Skill</span>
          </button>
        </form>
      </div>
    </div>
  );
};
