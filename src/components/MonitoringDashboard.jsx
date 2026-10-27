import { useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownToLine, Check, Circle, Database, Gauge, Radio, Server, ShieldAlert, Users } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useMonitoring } from '../hooks/useMonitoring';
import './MonitoringDashboard.css';

const intervals = [{ label: '5 min', minutes: 5 }, { label: '1 hora', minutes: 60 }, { label: '24 horas', minutes: 1440 }, { label: '7 dias', minutes: 10080 }];

export default function MonitoringDashboard() {
  const [minutes, setMinutes] = useState(60);
  const [pollMs, setPollMs] = useState(5000);
  const [activeTab, setActiveTab] = useState('Eventos');
  const { data, isLoading, isError, dataUpdatedAt, connection } = useMonitoring(minutes, pollMs);
  const series = data?.series || {};
  const events = data?.events || [];
  const trend = useMemo(() => {
    const source = series['http.request.duration_ms'] || series['http.requests.total'] || [];
    if (!source.length) return [];
    return source.map((point) => ({ time: new Date(point.at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }), value: point.value }));
  }, [series]);
  const serviceRows = [
    ['API', data?.status?.api || 'checking', Server],
    ['Banco de dados', data?.status?.database || 'checking', Database],
    ['Redis / fila', data?.status?.redis || 'disabled', Activity],
  ];
  const latestUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString('pt-BR') : '--:--:--';

  const exportEvents = () => {
    const columns = ['event_type', 'entity_type', 'occurred_at'];
    const csv = [columns.join(';'), ...events.map((event) => columns.map((column) => JSON.stringify(event[column] ?? '')).join(';'))].join('\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    link.download = 'eventos-monitoramento.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return <section className="monitoring-dashboard" aria-label="Central de monitoramento">
    <header className="monitoring-toolbar">
      <div><div className="monitor-eyebrow"><Gauge size={14} /> OBSERVABILIDADE DA PLATAFORMA</div><h2>Central de monitoramento</h2><p>Saúde dos serviços, eventos e métricas operacionais.</p></div>
      <div className="monitor-controls">
        <label><span>INTERVALO</span><select aria-label="Intervalo de monitoramento" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}>{intervals.map((option) => <option key={option.minutes} value={option.minutes}>{option.label}</option>)}</select></label>
        <label><span>ATUALIZAÇÃO</span><select aria-label="Frequência de atualização" value={pollMs} onChange={(event) => setPollMs(Number(event.target.value))}><option value={5000}>5 segundos</option><option value={10000}>10 segundos</option><option value={30000}>30 segundos</option><option value={0}>Pausada</option></select></label>
      </div>
    </header>

    <div className="environment-strip"><span><b>APLICAÇÃO</b> Aurora API</span><span><b>VERSÃO</b> 1.0.0</span><span><b>AMBIENTE</b> Desenvolvimento</span><span><b>REGIÃO</b> Local</span><span><b>RELÓGIO</b> {data?.server_time ? new Date(data.server_time).toLocaleTimeString('pt-BR') : '--:--:--'}</span><span className={`live-indicator ${connection}`}><i />{connection === 'live' ? 'AO VIVO' : connection === 'connecting' ? 'CONECTANDO' : 'POLLING / DESCONECTADO'}</span></div>

    {isError && <div className="monitor-error" role="alert"><AlertTriangle size={16} /> Falha ao consultar o monitoramento. O painel tentará novamente automaticamente.</div>}
    <div className="monitor-stat-grid">
      {serviceRows.map(([name, status, Icon]) => <article className={`monitor-stat ${status}`} key={name}><div className="monitor-stat-label"><Icon size={16} /><span>{name}</span></div><strong>{status === 'online' ? 'Operacional' : status === 'disabled' ? 'Não configurado' : status === 'offline' ? 'Indisponível' : 'Verificando'}</strong><small>{status === 'online' ? 'Verificado agora' : status === 'disabled' ? 'Redis opcional' : 'Estado atual'}</small><span className="stat-light" /></article>)}
      <article className="monitor-stat"><div className="monitor-stat-label"><Users size={16} /><span>Sessões ativas</span></div><strong>{isLoading ? '—' : data?.online_users ?? 0}</strong><small>Refresh tokens vigentes</small></article>
      <article className="monitor-stat"><div className="monitor-stat-label"><Radio size={16} /><span>Cadeia de auditoria</span></div><strong>{data?.event_chain_valid ? ' íntegra' : isLoading ? '—' : 'Verificar'}</strong><small>Hash encadeado</small></article>
      <article className="monitor-stat"><div className="monitor-stat-label"><Activity size={16} /><span>Última atualização</span></div><strong>{latestUpdate}</strong><small>{pollMs ? `A cada ${pollMs / 1000}s` : 'Atualização pausada'}</small></article>
    </div>

    <div className="monitor-panels-grid">
      <article className="monitor-panel resource-panel"><div className="monitor-panel-header"><div><span className="monitor-eyebrow">RECURSOS DO PROCESSO</span><h3>Uso da plataforma</h3></div><span className="monitor-tag">AMOSTRA ATUAL</span></div>
        <ResourceGauge label="CPU" value={data?.system?.cpu_percent} color="mint" />
        <ResourceGauge label="Memória do host" value={data?.system?.memory_percent} color="blue" />
        <ResourceGauge label="Pool de conexões" value={data?.system?.pool_occupancy_percent} color="amber" />
        <div className="resource-foot"><span>Memória do processo</span><strong>{data?.system?.process_memory_mb ?? 0} MB</strong></div>
      </article>
      <article className="monitor-panel trend-panel"><div className="monitor-panel-header"><div><span className="monitor-eyebrow">TELEMETRIA</span><h3>{series['http.request.duration_ms'] ? 'Latência HTTP' : 'Séries temporais'}</h3></div><span className="monitor-tag">{trend.length ? `${trend.length} PONTOS` : 'SEM AMOSTRAS'}</span></div>
        {trend.length ? <div className="monitor-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}><defs><linearGradient id="monitorFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#55c9a3" stopOpacity={0.28} /><stop offset="95%" stopColor="#55c9a3" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid stroke="#26332f" vertical={false} /><XAxis dataKey="time" tick={{ fill: '#82928b', fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: '#82928b', fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: '#18211e', border: '1px solid #34443d', borderRadius: 5, color: '#edf4ef', fontSize: 11 }} /><Area dataKey="value" type="monotone" stroke="#55c9a3" strokeWidth={2} fill="url(#monitorFill)" /></AreaChart></ResponsiveContainer></div> : <div className="empty-telemetry"><Activity size={22} /><strong>Aguardando amostras</strong><span>As séries aparecem após a coleta ou ingestão de métricas.</span></div>}
      </article>
    </div>

    <article className="monitor-panel event-panel"><div className="monitor-panel-header event-header"><div><span className="monitor-eyebrow">TRILHA OPERACIONAL</span><h3>Eventos e alertas</h3></div><div className="event-actions"><span className="monitor-tag">{events.length} EVENTOS NO INTERVALO</span><button className="monitor-export" onClick={exportEvents} disabled={!events.length}><ArrowDownToLine size={14} /> CSV</button></div></div>
      <div className="monitor-tabs" role="tablist" aria-label="Detalhes do monitoramento">{['Eventos', 'Alertas', 'Sessões'].map((tab) => <button key={tab} role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div>
      {activeTab === 'Eventos' ? <div className="event-table-wrap"><table className="event-table"><thead><tr><th>TIPO</th><th>MÓDULO</th><th>DATA / HORA</th><th>SEVERIDADE</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td><span className="event-kind"><Circle size={7} />{event.event_type}</span></td><td>{event.entity_type}</td><td>{new Date(event.occurred_at).toLocaleString('pt-BR')}</td><td><span className="event-severity">Informativo</span></td></tr>)}</tbody></table>{!events.length && <div className="empty-events">{isLoading ? 'Carregando eventos...' : 'Nenhum evento registrado neste intervalo.'}</div>}</div> : <div className="empty-events">{activeTab === 'Alertas' ? 'Nenhum alerta ativo.' : 'A lista detalhada de sessões está disponível na auditoria de acessos.'}</div>}
    </article>
    <footer className="monitor-footer"><span><ShieldAlert size={13} /> Dados agregados; informações pessoais permanecem mascaradas.</span><span><Check size={13} /> Atualizado {latestUpdate}</span></footer>
  </section>;
}

function ResourceGauge({ label, value = 0, color }) {
  const percentage = Math.min(100, Math.max(0, Number(value || 0)));
  const level = percentage >= 90 ? 'critical' : percentage >= 75 ? 'warning' : 'healthy';
  return <div className="resource-gauge"><div><span>{label}</span><strong>{Math.round(percentage)}%</strong></div><div className="resource-track"><span className={`${color} ${level}`} style={{ width: `${percentage}%` }} /></div></div>;
}
