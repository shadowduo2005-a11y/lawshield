import React, { useState, useEffect, useRef } from 'react';
import { Check, Zap } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const PLANS = [
  {
    name: 'Starter', monthly: 0, annual: 0,
    desc: 'For individuals exploring AI-powered legal tools.',
    cta: 'Get started free',
    features: ['10 AI prompts / month', 'Basic document analysis', 'Case law search', 'Community support'],
  },
  {
    name: 'Pro', monthly: 29, annual: 19,
    desc: 'Everything you need to practice at full speed.',
    cta: 'Start Pro trial', badge: 'Most popular', highlight: true,
    features: ['Unlimited AI prompts', 'Advanced document analysis', 'Motion drafting suite', 'Citation verification', 'Export to Word & PDF', 'Priority support'],
  },
  {
    name: 'Firm', monthly: 149, annual: 99,
    desc: 'For teams that need collaboration and workflows.',
    cta: 'Talk to sales',
    features: ['Everything in Pro', 'Unlimited team members', 'Shared workspaces', 'Custom templates', 'API access', 'Dedicated account manager'],
  },
];

const PricingSection = () => {
  const [annual, setAnnual] = useState(true);
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.p-header', { opacity: 0, y: 24 });
      gsap.set('.p-card', { opacity: 0, y: 40 });
      ScrollTrigger.create({
        trigger: ref.current, start: 'top 80%',
        onEnter: () => {
          gsap.to('.p-header', { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' });
          gsap.to('.p-card', { opacity: 1, y: 0, duration: 0.8, stagger: 0.15, ease: 'back.out(1.1)', delay: 0.2 });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section id="pricing" ref={ref} className="py-24 bg-slate-50 border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="p-header text-center max-w-xl mx-auto mb-10">
          <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-slate-400 bg-white border border-slate-200 rounded-full px-4 py-1.5 mb-4">
            Pricing
          </span>
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 mb-4">Simple, transparent pricing</h2>
          <p className="text-slate-500 text-base leading-relaxed mb-8">No hidden fees. Start free. Scale as you grow.</p>

          <div className="inline-flex items-center gap-1 bg-white border border-slate-200 rounded-full p-1">
            <button onClick={() => setAnnual(false)}
              className={`text-sm font-semibold px-5 py-2 rounded-full transition-all ${!annual ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
              Monthly
            </button>
            <button onClick={() => setAnnual(true)}
              className={`text-sm font-semibold px-5 py-2 rounded-full transition-all flex items-center gap-2 ${annual ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
              Annual
              <span className="text-[10px] font-bold text-emerald-600 bg-emerald-100 px-1.5 py-0.5 rounded-full">−35%</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-5xl mx-auto">
          {PLANS.map((plan) => (
            <div key={plan.name} className={`p-card flex flex-col rounded-2xl border p-7 transition-all duration-300 ${
              plan.highlight ? 'bg-slate-900 border-slate-900 shadow-2xl' : 'bg-white border-slate-200 hover:shadow-lg hover:border-slate-300'
            }`}>
              {plan.badge && (
                <div className="mb-4">
                  <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-white/70 border border-white/20 px-2.5 py-1 rounded-full">
                    <Zap size={9} /> {plan.badge}
                  </span>
                </div>
              )}

              <div className="mb-6">
                <div className={`text-xs font-bold uppercase tracking-wider mb-2 ${plan.highlight ? 'text-slate-400' : 'text-slate-400'}`}>
                  {plan.name}
                </div>
                <div className="flex items-end gap-1">
                  <span className={`text-4xl font-black tracking-tight ${plan.highlight ? 'text-white' : 'text-slate-900'}`}>
                    ${annual ? plan.annual : plan.monthly}
                  </span>
                  {(annual ? plan.annual : plan.monthly) > 0 && (
                    <span className={`text-sm mb-1.5 ${plan.highlight ? 'text-slate-400' : 'text-slate-400'}`}>/mo</span>
                  )}
                </div>
                <p className={`text-xs mt-2 leading-relaxed ${plan.highlight ? 'text-slate-400' : 'text-slate-400'}`}>
                  {plan.desc}
                </p>
              </div>

              <button className={`w-full text-sm font-semibold py-2.5 rounded-xl mb-6 transition-colors ${
                plan.highlight
                  ? 'bg-white text-slate-900 hover:bg-slate-100'
                  : 'bg-slate-900 text-white hover:bg-slate-700'
              }`}>
                {plan.cta}
              </button>

              <div className={`border-t mb-5 ${plan.highlight ? 'border-slate-700' : 'border-slate-100'}`} />

              <ul className="space-y-3 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className={`flex items-start gap-2.5 text-sm ${plan.highlight ? 'text-slate-300' : 'text-slate-600'}`}>
                    <Check size={14} className={`mt-0.5 shrink-0 ${plan.highlight ? 'text-white' : 'text-slate-900'}`} />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default PricingSection;
