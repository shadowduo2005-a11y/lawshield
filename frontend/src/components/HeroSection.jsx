import React, { useEffect, useRef } from 'react';
import { ArrowRight, Sparkles, ShieldCheck, FileText } from 'lucide-react';
import { gsap } from 'gsap';

const CHIPS = ['Draft a motion to dismiss', 'Summarize Roe v. Wade', 'Review NDA contract', 'Find CA precedents'];
const STATS = [
  { value: '10×', label: 'Faster drafting' },
  { value: '98%', label: 'Citation accuracy' },
  { value: '50K+', label: 'Legal professionals' },
];

const HeroSection = () => {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set(['.h-badge', '.h-title', '.h-sub', '.h-btn', '.h-stat', '.h-card'], { opacity: 0, y: 24 });
      const tl = gsap.timeline({ delay: 0.1 });
      tl.to('.h-badge', { opacity: 1, y: 0, duration: 0.6, ease: 'power3.out' })
        .to('.h-title',  { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' }, '-=0.3')
        .to('.h-sub',    { opacity: 1, y: 0, duration: 0.6, ease: 'power3.out' }, '-=0.3')
        .to('.h-btn',    { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }, '-=0.25')
        .to('.h-stat',   { opacity: 1, y: 0, duration: 0.5, stagger: 0.1, ease: 'power3.out' }, '-=0.2')
        .to('.h-card',   { opacity: 1, y: 0, duration: 0.8, ease: 'power4.out' }, '-=0.3');
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={ref} className="pt-28 pb-20 md:pt-36 md:pb-28 bg-white overflow-hidden">
      <div className="max-w-5xl mx-auto px-6 text-center">

        {/* Badge */}
        <div className="h-badge inline-flex items-center gap-2 bg-slate-100 border border-slate-200 text-slate-600 text-xs font-semibold rounded-full px-4 py-1.5 mb-6 shimmer-badge">
          <Sparkles size={12} className="text-amber-500" />
          Introducing lawShield 2.0 — AI for Legal Professionals
        </div>

        {/* Headline */}
        <h1 className="h-title text-5xl md:text-7xl font-extrabold tracking-tight text-slate-900 leading-[1.05] mb-5">
          Legal intelligence for{' '}
          <span className="text-slate-400">tomorrow's lawyers</span>
        </h1>

        <p className="h-sub text-lg md:text-xl text-slate-500 max-w-2xl mx-auto leading-relaxed mb-8">
          Draft court-ready motions, analyze contracts, and surface winning case law — in seconds.
        </p>

        {/* CTA buttons */}
        <div className="h-btn flex flex-wrap items-center justify-center gap-3 mb-10">
          <a href="/app" className="inline-flex items-center gap-2 bg-slate-900 text-white font-semibold px-7 py-3 rounded-full hover:bg-slate-700 transition-colors shadow-lg">
            Start for free <ArrowRight size={15} />
          </a>
          <button className="inline-flex items-center gap-2 border border-slate-200 text-slate-700 font-medium px-6 py-3 rounded-full hover:bg-slate-50 transition-colors">
            Watch demo
          </button>
        </div>

        {/* Stats row */}
        <div className="flex flex-wrap items-center justify-center gap-10 mb-14">
          {STATS.map((s) => (
            <div key={s.label} className="h-stat text-center">
              <div className="text-2xl font-black text-slate-900 tracking-tight">{s.value}</div>
              <div className="text-xs text-slate-400 mt-0.5 font-medium">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Hero UI card */}
        <div className="h-card max-w-3xl mx-auto rounded-2xl border border-slate-200 bg-white shadow-xl overflow-hidden">
          {/* Browser chrome */}
          <div className="flex items-center gap-1.5 px-4 py-3 bg-slate-50 border-b border-slate-200">
            <div className="w-3 h-3 rounded-full bg-red-400/70" />
            <div className="w-3 h-3 rounded-full bg-amber-400/70" />
            <div className="w-3 h-3 rounded-full bg-green-400/70" />
            <div className="flex-1 flex justify-center">
              <div className="bg-white border border-slate-200 rounded px-4 py-0.5 text-xs text-slate-400 font-mono w-44 text-center">
                app.lawshield.ai
              </div>
            </div>
          </div>

          {/* App body */}
          <div className="p-5 md:p-7 text-left">
            {/* Input */}
            <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 mb-4">
              <Sparkles size={15} className="text-slate-400 shrink-0" />
              <span className="text-sm text-slate-400 flex-1">
                Draft a motion to suppress evidence in People v. Martinez…
              </span>
              <div className="w-7 h-7 rounded-lg bg-slate-900 flex items-center justify-center shrink-0">
                <ArrowRight size={12} className="text-white" />
              </div>
            </div>

            {/* Chips */}
            <div className="flex flex-wrap gap-2 mb-5">
              {CHIPS.map((c) => (
                <span key={c} className="px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs text-slate-600 cursor-pointer hover:bg-slate-200 transition-colors">
                  {c}
                </span>
              ))}
            </div>

            {/* AI response card */}
            <div className="border border-slate-200 rounded-xl p-4 bg-slate-50">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-5 h-5 rounded-full bg-slate-900 flex items-center justify-center">
                  <Sparkles size={9} className="text-white" />
                </div>
                <span className="text-xs font-semibold text-slate-700">lawShield AI</span>
                <span className="ml-auto text-[10px] text-slate-400 bg-white border border-slate-200 px-2 py-0.5 rounded-full font-mono">Just now</span>
              </div>
              <div className="space-y-2 mb-4">
                <div className="h-2.5 bg-slate-200 rounded-full w-4/5" />
                <div className="h-2.5 bg-slate-200 rounded-full w-full" />
                <div className="h-2.5 bg-slate-200 rounded-full w-3/5" />
              </div>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-[11px] text-emerald-700 font-semibold bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
                  <ShieldCheck size={10} /> 3 citations verified
                </span>
                <span className="flex items-center gap-1 text-[11px] text-blue-700 font-semibold bg-blue-50 border border-blue-200 px-2.5 py-1 rounded-full">
                  <FileText size={10} /> Ready to export
                </span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
};

export default HeroSection;
