import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api, { getAccessToken, renewAccessToken } from '../services/api';

export function useMonitoring(minutes = 60) {
  const queryClient = useQueryClient();
  const [connection, setConnection] = useState('connecting');
  const { data, isLoading, isError, dataUpdatedAt } = useQuery({
    queryKey: ['monitoring', minutes],
    queryFn: async () => (await api.get('/monitoramento/central', { params: { minutes } })).data,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });

  useEffect(() => {
    let stopped = false;
    let socket;
    let reconnectTimer;
    let retryDelay = 1000;
    const token = getAccessToken();
    if (!token) {
      setConnection('disconnected');
      return () => { stopped = true; };
    }

    const connect = () => {
      if (stopped) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const afterId = Number(sessionStorage.getItem('aurora.monitoring.after-id') || 0);
      const url = `${protocol}//${window.location.host}/api/v1/monitoramento/ws?token=${encodeURIComponent(token)}&channel=all&after_id=${afterId}`;
      socket = new WebSocket(url);
      socket.onopen = () => { retryDelay = 1000; setConnection('live'); };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.id) sessionStorage.setItem('aurora.monitoring.after-id', String(message.id));
          if (message.type !== 'heartbeat') queryClient.invalidateQueries({ queryKey: ['monitoring'] });
        } catch {
          queryClient.invalidateQueries({ queryKey: ['monitoring'] });
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = (event) => {
        setConnection('disconnected');
        if (!stopped) {
          if (event.code === 4401) {
            renewAccessToken().then(connect).catch(() => window.dispatchEvent(new Event('aurora:session-expired')));
            return;
          }
          reconnectTimer = window.setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 30000);
        }
      };
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [queryClient]);

  return { data, isLoading, isError, dataUpdatedAt, connection };
}
