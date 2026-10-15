import React, { useEffect, useRef } from 'react';
import { MessageSquare, FileText, ShieldCheck } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const DEMOS = [
  {
    Icon: MessageSquare, label: 'AI Chat', tag: 'Research',
    prompt: 'What are the elements of promissory estoppel?',
    response: '(1) A clear promise, (2) reasonable reliance, (3) detrimental change in position, (4) injustice if not enforced...',
  },
  {
    Icon: FileText, label: 'Document Review', tag: 'Contract',
    prompt: 'Analyze clause 4.2 of this NDA',
    response: '⚠ Risk: Clause 4.2 contains a perpetual non-compete with no geographic limit. Recommend redline.',
    elevated: true,
  },
  {
    Icon: ShieldCheck, label: 'Citation Check', tag: 'Verify',
    prompt: 'Verify citations in my motion brief',
    response: '✓ 14 citations verified against Westlaw. 1 updated — Miranda v. Arizona (1966) corrected.',
  },
];

const DemoCTASection = () => {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.d-header', { opacity: 0, y: 24 });
      gsap.set('.d-card', { opacity: 0, y: 30 });
      ScrollTrigger.create({
        trigger: ref.current, start: 'top 80%',
        onEnter: () => {
          gsap.to('.d-header', { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' });
          gsap.to('.d-card', { opacity: 1, y: 0, duration: 0.65, stagger: 0.15, ease: 'power3.out', delay: 0.2 });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={ref} className="py-24 bg-slate-50 border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="d-header text-center max-w-2xl mx-auto mb-14">
          <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-slate-400 bg-white border border-slate-200 rounded-full px-4 py-1.5 mb-4">
            See it in action
          </span>
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 mb-4">
            One tool, every legal task
          </h2>
          <p className="text-slate-500 text-base leading-relaxed">
            From research to drafting to document review — lawShield handles it in one unified workspace.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl mx-auto mb-10">
          {DEMOS.map((d, i) => {
            const Icon = d.Icon;
            return (
              <div key={i} className={`d-card bg-white border border-slate-200 rounded-2xl p-5 flex flex-col transition-all duration-300 hover:shadow-lg hover:border-slate-300 ${d.elevated ? 'md:-translate-y-4 shadow-lg border-slate-300' : ''}`}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Icon size={14} className="text-slate-400" />
                    <span className="text-xs font-semibold text-slate-500">{d.label}</span>
                  </div>
                  <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{d.tag}</span>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
                  <p className="text-xs text-slate-700 leading-relaxed">"{d.prompt}"</p>
                </div>
                <div className="flex gap-2 mt-auto">
                  <div className="w-5 h-5 rounded-full bg-slate-900 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[8px] font-black text-white">AI</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{d.response}</p>
                </div>
              </div>
            );
          })}
        </div>

        <div className="text-center">
          <button className="inline-flex items-center gap-2 bg-slate-900 text-white font-semibold px-7 py-3 rounded-full hover:bg-slate-700 transition-colors shadow-lg">
            Try it yourself — free
          </button>
        </div>
      </div>
    </section>
  );
};

export default DemoCTASection;
