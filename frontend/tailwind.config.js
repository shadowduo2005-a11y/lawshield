/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['Playfair Display', 'Georgia', 'serif'],
      },
      colors: {
        ink: '#0a0a0a',
        muted: '#6b7280',
        subtle: '#9ca3af',
        surface: '#f9fafb',
        border: '#e5e7eb',
      },
      boxShadow: {
        'xs': '0 1px 3px rgba(0,0,0,0.05)',
        'card': '0 4px 16px -4px rgba(0,0,0,0.08)',
        'card-hover': '0 12px 40px -8px rgba(0,0,0,0.14)',
        'cta': '0 24px 60px -12px rgba(0,0,0,0.18)',
      },
      borderRadius: {
        'xl': '0.875rem',
        '2xl': '1.25rem',
        '3xl': '1.5rem',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      }
    },
  },
  plugins: [],
}
