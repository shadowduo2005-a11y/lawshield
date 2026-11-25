import React, { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';

const NAV_LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'Solutions', href: '#solutions' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
];

const Navbar = () => {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
      scrolled ? 'bg-white/90 backdrop-blur-xl border-b border-slate-200 shadow-sm' : 'bg-transparent'
    }`}>
      <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-16">
        <a href="/" className="text-lg font-bold tracking-tight text-slate-900">
          law<span className="text-slate-400">Shield</span>
        </a>

        <div className="hidden md:flex items-center gap-7">
          {NAV_LINKS.map((link) => (
            <a key={link.label} href={link.href}
              className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors">
              {link.label}
            </a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          <a href="/login" className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors px-3 py-2">
            Log in
          </a>
          <a href="/app" className="bg-slate-900 text-white text-sm font-semibold px-5 py-2 rounded-full hover:bg-slate-700 transition-colors">
            Get started
          </a>
        </div>

        <button className="md:hidden p-2 text-slate-500 hover:text-slate-900"
          onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {menuOpen && (
        <div className="md:hidden bg-white border-b border-slate-200 px-6 py-4 flex flex-col gap-4">
          {NAV_LINKS.map((link) => (
            <a key={link.label} href={link.href}
              className="text-sm font-medium text-slate-600 hover:text-slate-900"
              onClick={() => setMenuOpen(false)}>
              {link.label}
            </a>
          ))}
          <div className="border-t border-slate-200 pt-3 flex flex-col gap-2">
            <a href="/login" className="w-full text-center text-sm font-medium text-slate-600 border border-slate-200 rounded-full py-2 hover:bg-slate-50">Log in</a>
            <a href="/app" className="w-full text-center text-sm font-semibold bg-slate-900 text-white rounded-full py-2 hover:bg-slate-700">Get started</a>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
