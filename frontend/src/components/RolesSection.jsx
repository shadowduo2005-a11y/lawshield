import React, { useState, useEffect, useRef } from 'react';
import { ChevronRight, Scale, BookOpen, GraduationCap } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const ROLES = [
  {
    id: 'litigation', Icon: Scale, title: 'Litigation Attorneys', headline: 'Win more cases, faster.',
    desc: 'Generate motions, find supporting case law, and build your trial narrative with AI that understands courtroom strategy.',
    bullets: ['Motion drafting in minutes', 'Jurisdiction-aware research', 'Cross-examination prep'],
  },
  {
    id: 'corporate', Icon: BookOpen, title: 'Corporate & In-House', headline: 'Review contracts in seconds.',
    desc: 'Identify risk clauses, flag unusual terms, and get redline suggestions across any commercial agreement without burning out your team.',
    bullets: ['Full contract risk scoring', 'Clause library comparison', 'Redline generation'],
  },
  {
    id: 'students', Icon: GraduationCap, title: 'Law Students', headline: 'Study smarter, not harder.',
    desc: 'Brief cases instantly, master complex doctrines with plain-English explanations, and practice applying legal reasoning to hypotheticals.',
    bullets: ['Case briefing in 30 seconds', 'Doctrine deep-dives', 'Practice exam mode'],
  },
];

const RolesSection = () => {
  const [active, setActive] = useState('litigation');
  const ref = useRef(null);
  const role = ROLES.find((r) => r.id === active);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.r-left', { opacity: 0, x: -30 });
      gsap.set('.r-right', { opacity: 0, x: 30 });
      ScrollTrigger.create({
        trigger: ref.current, start: 'top 78%',
        onEnter: () => {
          gsap.to('.r-left',  { opacity: 1, x: 0, duration: 0.8, ease: 'power3.out' });
          gsap.to('.r-right', { opacity: 1, x: 0, duration: 0.8, ease: 'power3.out', delay: 0.1 });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section id="solutions" ref={ref} className="py-24 bg-slate-50 border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center max-w-xl mx-auto mb-14">
          <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-slate-400 bg-white border border-slate-200 rounded-full px-4 py-1.5 mb-4">
            Solutions
          </span>
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 mb-4">The right tools for your role</h2>
          <p className="text-slate-500 text-base leading-relaxed">lawShield adapts to how you practice law, not the other way around.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          {/* Left: role tabs */}
          <div className="r-left space-y-3">
            {ROLES.map((r) => {
              const Icon = r.Icon;
              const isActive = active === r.id;
              return (
                <button key={r.id} onClick={() => setActive(r.id)}
                  className={`w-full text-left p-5 rounded-2xl border transition-all duration-300 ${
                    isActive ? 'bg-white border-slate-900 shadow-md' : 'bg-white border-slate-200 hover:border-slate-300'
                  }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Icon size={15} className={isActive ? 'text-slate-900' : 'text-slate-400'} />
                      <span className={`text-sm font-semibold ${isActive ? 'text-slate-900' : 'text-slate-500'}`}>
                        {r.title}
                      </span>
                    </div>
                    <ChevronRight size={14} className={`transition-transform duration-300 ${isActive ? 'rotate-90 text-slate-900' : 'text-slate-300'}`} />
                  </div>
                  {isActive && (
                    <div className="mt-3 pt-3 border-t border-slate-200">
                      <p className="text-sm text-slate-500 mb-3 leading-relaxed">{r.desc}</p>
                      <ul className="space-y-1.5">
                        {r.bullets.map((b) => (
                          <li key={b} className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                            <div className="w-1.5 h-1.5 rounded-full bg-slate-900 shrink-0" />
                            {b}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Right: preview */}
          <div className="r-right bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center text-white">
                <role.Icon size={13} />
              </div>
              <span className="text-sm font-bold text-slate-900">{role.title}</span>
            </div>
            <h3 className="text-2xl font-extrabold text-slate-900 mb-2">{role.headline}</h3>
            <p className="text-sm text-slate-500 leading-relaxed mb-6">{role.desc}</p>
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-xs font-semibold text-slate-700">AI Response ready</span>
              </div>
              <div className="space-y-2">
                <div className="h-2 bg-slate-200 rounded-full w-full" />
                <div className="h-2 bg-slate-200 rounded-full w-4/5" />
                <div className="h-2 bg-slate-200 rounded-full w-3/5" />
              </div>
            </div>
            <button className="w-full flex items-center justify-center gap-2 bg-slate-900 text-white text-sm font-semibold py-2.5 rounded-xl hover:bg-slate-700 transition-colors">
              Try {role.title} <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default RolesSection;
