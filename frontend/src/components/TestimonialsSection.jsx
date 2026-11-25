import React, { useEffect, useRef } from 'react';
import { Star, Quote } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const REVIEWS = [
  { name: 'Sarah Jenkins', role: 'Managing Partner, Jenkins & Cole LLP', text: 'lawShield completely transformed our workflow. We draft motions in a fraction of the time, and citation accuracy is remarkable.', rating: 5 },
  { name: 'Michael Chen', role: 'Defense Attorney, San Francisco', text: 'The ability to summarize dense case law overnight is a game changer. It\'s like having an entire team of paralegals on demand.', rating: 5, featured: true },
  { name: 'Elena Rodriguez', role: 'General Counsel, TechStartup Inc.', text: 'Reviewing contracts used to take hours. Now I surface key clauses and risks in minutes. My CEO loves the turnaround time.', rating: 5 },
  { name: 'David Kim', role: 'Associate, Sullivan & Cromwell', text: 'I was skeptical about AI in law. But the drafts are actually court-ready, not just rough outlines. It saved me during a tight deadline.', rating: 5 },
  { name: 'Jessica Patel', role: 'Solo Practitioner', text: 'As a solo practitioner, lawShield gives me the research capabilities of a large firm. I genuinely couldn\'t compete without it.', rating: 5 },
];

const TestimonialsSection = () => {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set('.t-header', { opacity: 0, y: 24 });
      gsap.set('.t-card', { opacity: 0, y: 30 });
      ScrollTrigger.create({
        trigger: ref.current, start: 'top 80%',
        onEnter: () => {
          gsap.to('.t-header', { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' });
          gsap.to('.t-card', { opacity: 1, y: 0, duration: 0.6, stagger: 0.08, ease: 'power3.out', delay: 0.2 });
        },
      });
    }, ref);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={ref} className="py-24 bg-white border-t border-slate-100">
      <div className="max-w-6xl mx-auto px-6">
        <div className="t-header text-center max-w-xl mx-auto mb-14">
          <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-slate-400 bg-slate-100 border border-slate-200 rounded-full px-4 py-1.5 mb-4">
            Testimonials
          </span>
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 mb-4">
            Trusted by legal professionals
          </h2>
          <p className="text-slate-500 text-base leading-relaxed">From solo practitioners to BigLaw associates — real lawyers, real results.</p>
        </div>

        <div className="columns-1 md:columns-2 lg:columns-3 gap-4 space-y-4">
          {REVIEWS.map((r, i) => (
            <div key={i} className={`t-card break-inside-avoid bg-white border rounded-2xl p-6 ${r.featured ? 'border-slate-900 shadow-lg' : 'border-slate-200 hover:border-slate-300 hover:shadow-md transition-all'}`}>
              <Quote size={16} className="text-slate-200 mb-3" />
              <div className="flex gap-0.5 mb-3">
                {Array.from({ length: r.rating }).map((_, j) => (
                  <Star key={j} size={11} className="text-amber-400 fill-amber-400" />
                ))}
              </div>
              <p className="text-sm text-slate-700 leading-relaxed mb-4">"{r.text}"</p>
              <div className="flex items-center gap-3 pt-3 border-t border-slate-100">
                <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-xs font-bold text-slate-500">
                  {r.name.split(' ').map((n) => n[0]).join('')}
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">{r.name}</div>
                  <div className="text-[11px] text-slate-400">{r.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default TestimonialsSection;
