import React, { useEffect, useRef } from 'react';
import { MessageSquare, FileText, Lightbulb, ShieldCheck, Zap, BookOpen } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const FEATURES = [
  { icon: MessageSquare, title: 'AI Legal Chat', desc: 'Ask anything — get precise, source-cited answers powered by the latest case law and statutes.', tag: 'Core', tagColor: 'bg-slate-100 text-slate-500' },
  { icon: FileText, title: 'Document Analysis', desc: 'Drop in a contract. Get a full risk breakdown, key obligations, and redlines in seconds.', tag: 'Popular', tagColor: 'bg-amber-50 text-amber-600' },
  { icon: Lightbulb, title: 'Case Strategy Builder', desc: 'Generate tactical approaches based on historical precedents and your jurisdiction.', tag: 'New', tagColor: 'bg-emerald-50 text-emerald-600' },
  { icon: ShieldCheck, title: 'Citation Verification', desc: 'Every AI reference is validated against real case databases. No hallucinated citations.', tag: 'Core', tagColor: 'bg-slate-100 text-slate-500' },
  { icon: Zap, title: 'Motion Drafting', desc: 'Generate court-ready first drafts for motions, briefs, and pleadings with one sentence.', tag: 'Popular', tagColor: 'bg-amber-50 text-amber-600' },
  { icon: BookOpen, title: 'Deposition Summaries', desc: 'Upload a transcript. Get a concise summary with key statements and contradictions flagged.', tag: 'Core', tagColor: 'bg-slate-100 text-slate-500' },
];

const FeaturesSection = () => {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.f-header', { opacity: 0, y: 24 });
      gsap.set('.f-card', { opacity: 0, y: 30 });

      ScrollTrigger.create({
        trigger: ref.current,
        start: 'top 80%',
        onEnter: () => {
          gsap.to('.f-header', { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' });
          gsap.to('.f-card', { opacity: 1, y: 0, duration: 0.6, stagger: 0.08, ease: 'power3.out', delay: 0.2 });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section id="features" ref={ref} className="py-24 bg-white border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="f-header text-center max-w-2xl mx-auto mb-14">
          <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-slate-400 bg-slate-100 border border-slate-200 rounded-full px-4 py-1.5 mb-4">
            Features
          </span>
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 mb-4">
            Built for how lawyers actually work
          </h2>
          <p className="text-slate-500 text-base leading-relaxed">
            Every feature is designed around the high-stakes demands of legal professionals — not generic AI fluff.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <div key={i} className="f-card group bg-white border border-slate-200 rounded-2xl p-6 hover:border-slate-300 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
                <div className="flex items-start justify-between mb-5">
                  <div className="w-9 h-9 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center group-hover:bg-slate-900 group-hover:border-slate-900 transition-all duration-300">
                    <Icon size={16} className="text-slate-600 group-hover:text-white transition-colors duration-300" />
                  </div>
                  <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full ${f.tagColor}`}>
                    {f.tag}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-slate-900 mb-2">{f.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default FeaturesSection;
