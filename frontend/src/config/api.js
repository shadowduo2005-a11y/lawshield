const configuredUrl = import.meta.env.VITE_API_URL?.trim().replace(/\/+$/, '');

// VITE_* values are embedded at build time. Local development keeps the
// convenient port-3000 default; production must set VITE_API_URL in Vercel.
export const API = configuredUrl
  || (import.meta.env.DEV ? 'http://localhost:3000/api' : '/api');

if (import.meta.env.PROD && !configuredUrl) {
  console.error('VITE_API_URL is missing. Set it in Vercel and redeploy.');
}
