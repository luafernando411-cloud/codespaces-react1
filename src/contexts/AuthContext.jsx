import { createContext, useContext, useEffect, useState } from 'react';
import api, { setAccessToken } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const refreshToken = sessionStorage.getItem('aurora.refresh');
    if (!refreshToken) {
      setLoading(false);
      return () => { mounted = false; };
    }
    api.post('/auth/refresh', { refresh_token: refreshToken })
      .then(({ data }) => {
        if (!mounted) return;
        setAccessToken(data.access_token);
        sessionStorage.setItem('aurora.refresh', data.refresh_token);
        return api.get('/auth/me');
      })
      .then(({ data }) => { if (mounted && data) setUser(data); })
      .catch(() => {
        setAccessToken(null);
        sessionStorage.removeItem('aurora.refresh');
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    const expireSession = () => { setUser(null); setAccessToken(null); };
    window.addEventListener('aurora:session-expired', expireSession);
    return () => window.removeEventListener('aurora:session-expired', expireSession);
  }, []);

  const login = async (cpf, password) => {
    const { data } = await api.post('/auth/login', { cpf: cpf.replace(/\D/g, ''), password });
    setAccessToken(data.access_token);
    sessionStorage.setItem('aurora.refresh', data.refresh_token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    const refreshToken = sessionStorage.getItem('aurora.refresh');
    try {
      if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken });
    } finally {
      setAccessToken(null);
      sessionStorage.removeItem('aurora.refresh');
      setUser(null);
    }
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return context;
}
