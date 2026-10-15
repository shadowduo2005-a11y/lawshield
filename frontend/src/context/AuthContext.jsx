import React, { createContext, useState, useEffect, useCallback } from 'react';

export const AuthContext = createContext(null);

const API = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [user, setUser]   = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Fetch current user profile ──────────────────────────────────────────────
  const fetchUser = useCallback(async (currentToken) => {
    if (!currentToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${currentToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        // Token is invalid or expired – clear it
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
      }
    } catch {
      // Network error – keep token, user stays null, allow retry
    } finally {
      setLoading(false);
    }
  }, []);

  // Run once on mount (and whenever token changes)
  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      fetchUser(token);
    } else {
      localStorage.removeItem('token');
      setUser(null);
      setLoading(false);
    }
  }, [token, fetchUser]);

  // ── Login ───────────────────────────────────────────────────────────────────
  const login = async (email, password) => {
    const res = await fetch(`${API}/auth/login`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.msg || 'Login failed.');
    setToken(data.token);
  };

  // ── Register ────────────────────────────────────────────────────────────────
  const register = async (name, email, password) => {
    const res = await fetch(`${API}/auth/register`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ name, email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.msg || 'Registration failed.');
    setToken(data.token);
  };

  // ── Logout ──────────────────────────────────────────────────────────────────
  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
