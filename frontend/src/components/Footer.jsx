import React from 'react';

const LINKS = {
  Product: ['Features', 'Pricing', 'Changelog', 'Roadmap'],
  Solutions: ['Litigation', 'Corporate', 'Law Students', 'Solo Practice'],
  Company: ['About', 'Blog', 'Careers', 'Press'],
  Legal: ['Privacy Policy', 'Terms of Service', 'Security', 'Cookies'],
};

const Footer = () => (
  <footer className="border-t border-slate-100 bg-white pt-14 pb-8">
    <div className="max-w-6xl mx-auto px-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
        <div className="col-span-2 md:col-span-1">
          <a href="/" className="text-lg font-bold tracking-tight text-slate-900 block mb-3">
            law<span className="text-slate-400">Shield</span>
          </a>
          <p className="text-xs text-slate-400 leading-relaxed max-w-[175px]">
            AI-powered legal intelligence for the modern legal professional.
          </p>
        </div>
        {Object.entries(LINKS).map(([group, links]) => (
          <div key={group}>
            <h4 className="text-[10px] font-bold text-slate-900 uppercase tracking-widest mb-4">{group}</h4>
            <ul className="space-y-2.5">
              {links.map((link) => (
                <li key={link}>
                  <a href="#" className="text-sm text-slate-400 hover:text-slate-700 transition-colors">{link}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-100 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-xs text-slate-300">© {new Date().getFullYear()} lawShield, Inc. All rights reserved.</p>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span className="text-xs text-slate-400">All systems operational</span>
        </div>
      </div>
    </div>
  </footer>
);

export default Footer;
