import React, { useState, useEffect, useRef } from 'react';
import { Plus, Minus } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const FAQS = [
  { q: 'Is my client data secure?', a: 'Yes. lawShield uses enterprise-grade AES-256 encryption at rest and in transit. Your client data is never used to train our models, and you retain full ownership of everything you upload.' },
  { q: 'Can it generate full court-ready documents?', a: 'lawShield generates comprehensive first drafts — including motions, briefs, and pleadings. These are designed to be reviewed and finalized by a qualified attorney.' },
  { q: 'How does it handle jurisdiction-specific law?', a: 'You can filter research and drafting by specific state or federal jurisdictions. Our database covers all 50 states plus federal circuits with regular updates.' },
  { q: 'What AI model does lawShield use?', a: 'We use frontier language models fine-tuned specifically on legal corpora, combined with verified case law databases including Westlaw and LexisNexis-indexed sources.' },
  { q: 'Do you offer a free trial?', a: 'Yes — our Starter plan is permanently free with 10 AI prompts per month. For Pro, we offer a 14-day free trial with no credit card required.' },
  { q: 'Can I integrate with my existing tools?', a: 'Firm plan users get full API access and can integrate with Clio, MyCase, PracticePanther, and most major practice management systems.' },
];

const FAQSection = () => {
  const [openIdx, setOpenIdx] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.fq-col', { opacity: 0, y: 24 });
      ScrollTrigger.create({
        trigger: ref.current, start: 'top 80%',
        onEnter: () => {
          gsap.to('.fq-col', { opacity: 1, y: 0, duration: 0.7, stagger: 0.15, ease: 'power3.out' });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section id="faq" ref={ref} className="py-24 bg-white border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">

          {/* Left */}
          <div className="fq-col">
            <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-slate-400 bg-slate-100 border border-slate-200 rounded-full px-4 py-1.5 mb-4">
              FAQ
            </span>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 mb-4 leading-tight">
              Frequently asked questions
            </h2>
            <p className="text-sm text-slate-500 leading-relaxed mb-6">
              Can't find what you're looking for? Reach us at{' '}
              <a href="mailto:support@lawshield.ai" className="text-slate-900 font-semibold underline underline-offset-2">
                support@lawshield.ai
              </a>
            </p>
            <button className="text-sm font-semibold text-slate-700 border border-slate-200 rounded-full px-5 py-2 hover:bg-slate-50 transition-colors">
              Contact support
            </button>
          </div>

          {/* Right: accordion */}
          <div className="fq-col lg:col-span-2 space-y-3">
            {FAQS.map((item, i) => (
              <div key={i} className={`border rounded-xl overflow-hidden transition-colors duration-200 ${openIdx === i ? 'border-slate-300' : 'border-slate-200'}`}>
                <button onClick={() => setOpenIdx(openIdx === i ? -1 : i)}
                  className="w-full flex items-center justify-between p-5 text-left bg-white hover:bg-slate-50 transition-colors">
                  <span className="text-sm font-semibold text-slate-900 pr-4">{item.q}</span>
                  <span className={`shrink-0 w-6 h-6 rounded-full border flex items-center justify-center transition-all duration-200 ${
                    openIdx === i ? 'bg-slate-900 border-slate-900 text-white' : 'border-slate-200 text-slate-400'
                  }`}>
                    {openIdx === i ? <Minus size={11} /> : <Plus size={11} />}
                  </span>
                </button>
                <div className={`overflow-hidden transition-all duration-300 ease-in-out ${openIdx === i ? 'max-h-56' : 'max-h-0'}`}>
                  <p className="px-5 pb-5 pt-0 text-sm text-slate-500 leading-relaxed border-t border-slate-100 pt-3 bg-white">
                    {item.a}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default FAQSection;
