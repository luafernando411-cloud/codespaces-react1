import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

let accessToken = null;
let refreshPromise = null;

export function setAccessToken(token) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export async function renewAccessToken() {
  const refreshToken = sessionStorage.getItem('aurora.refresh');
  if (!refreshToken) throw new Error('Sessao inexistente');
  const { data } = await api.post('/auth/refresh', { refresh_token: refreshToken });
  accessToken = data.access_token;
  sessionStorage.setItem('aurora.refresh', data.refresh_token);
  return data.access_token;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

api.interceptors.response.use((response) => response, async (error) => {
  const request = error.config;
  const refreshToken = sessionStorage.getItem('aurora.refresh');
  if (error.response?.status !== 401 || !refreshToken || request?._retry || request?.url?.includes('/auth/')) {
    return Promise.reject(error);
  }
  request._retry = true;
  try {
    refreshPromise ||= api.post('/auth/refresh', { refresh_token: refreshToken })
      .then(({ data }) => {
        accessToken = data.access_token;
        sessionStorage.setItem('aurora.refresh', data.refresh_token);
        return data.access_token;
      })
      .finally(() => { refreshPromise = null; });
    const renewedToken = await refreshPromise;
    request.headers.Authorization = `Bearer ${renewedToken}`;
    return api(request);
  } catch (refreshError) {
    accessToken = null;
    sessionStorage.removeItem('aurora.refresh');
    window.dispatchEvent(new Event('aurora:session-expired'));
    return Promise.reject(refreshError);
  }
});

export default api;
