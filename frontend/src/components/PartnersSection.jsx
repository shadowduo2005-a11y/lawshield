import React from 'react';

const PARTNERS = ['Cravath & Partners', 'Morrison Foerster', 'Sidley Austin', 'WilmerHale', 'Gibson Dunn', 'Skadden Arps'];

const PartnersSection = () => (
  <section className="py-10 border-y border-slate-100 bg-slate-50">
    <div className="max-w-6xl mx-auto px-6">
      <p className="text-center text-[11px] font-bold text-slate-300 uppercase tracking-widest mb-6">
        Trusted by leading firms worldwide
      </p>
      <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
        {PARTNERS.map((name) => (
          <span key={name} className="text-sm font-semibold text-slate-300 hover:text-slate-500 transition-colors cursor-default tracking-tight">
            {name}
          </span>
        ))}
      </div>
    </div>
  </section>
);

export default PartnersSection;
