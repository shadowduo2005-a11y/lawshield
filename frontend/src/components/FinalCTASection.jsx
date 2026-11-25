import React, { useEffect, useRef } from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const FinalCTASection = () => {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.cta-inner', { opacity: 0, y: 30, scale: 0.98 });
      ScrollTrigger.create({
        trigger: ref.current, start: 'top 84%',
        onEnter: () => {
          gsap.to('.cta-inner', { opacity: 1, y: 0, scale: 1, duration: 0.9, ease: 'power3.out' });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={ref} className="py-20 bg-white border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="cta-inner bg-slate-900 rounded-3xl px-8 py-14 md:px-14 md:py-20 relative overflow-hidden">
          {/* Orbs */}
          <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-white/5 pointer-events-none" />
          <div className="absolute -bottom-12 -left-12 w-48 h-48 rounded-full bg-white/5 pointer-events-none" />

          <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-10">
            <div className="max-w-lg text-center md:text-left">
              <div className="inline-flex items-center gap-2 bg-white/10 border border-white/15 text-slate-300 text-xs font-semibold rounded-full px-4 py-1.5 mb-5">
                <ShieldCheck size={11} /> Enterprise-grade security · SOC 2 compliant
              </div>
              <h2 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-tight mb-4">
                Ready to transform your legal practice?
              </h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                Join 50,000+ legal professionals who trust lawShield to research faster, draft better, and win more.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row md:flex-col gap-3 shrink-0">
              <button className="inline-flex items-center justify-center gap-2 bg-white text-slate-900 font-semibold text-sm px-7 py-3 rounded-full hover:bg-slate-100 transition-colors">
                Start for free <ArrowRight size={14} />
              </button>
              <button className="inline-flex items-center justify-center gap-2 border border-white/20 text-slate-300 font-medium text-sm px-7 py-3 rounded-full hover:bg-white/10 hover:text-white transition-colors">
                Book a demo
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default FinalCTASection;
