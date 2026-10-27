import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Check, Clock3, RotateCcw, Save, ShieldCheck } from 'lucide-react';
import api from '../services/api';

export default function EnterpriseSettings() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');
  const parameters = useQuery({ queryKey: ['system-parameters'], queryFn: async () => (await api.get('/configuracoes/parametros')).data });
  const approvals = useQuery({ queryKey: ['parameter-approvals'], queryFn: async () => (await api.get('/configuracoes/aprovacoes')).data });
  const seed = useMutation({
    mutationFn: () => api.post('/configuracoes/parametros/seed'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['system-parameters'] }),
  });
  const review = useMutation({
    mutationFn: ({ id, decision }) => api.post(`/configuracoes/aprovacoes/${id}/revisao`, { decision, reason: decision === 'aprovado' ? 'Revisado por segundo Super Administrador' : 'Rejeitado na revisao administrativa' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['parameter-approvals'] }),
  });

  const complete = (result) => {
    queryClient.invalidateQueries({ queryKey: ['system-parameters'] });
    setMessage(result.status === 'aguardando_aprovacao' ? 'Alteração sensível enviada para aprovação por outro Super Administrador.' : 'Parâmetro aplicado e versionado.');
  };

  return <section className="enterprise-settings">
    <header className="settings-heading"><div><div className="eyebrow"><ShieldCheck size={14} /> GOVERNANÇA DO SISTEMA</div><h2>Configurações</h2><p>Parâmetros com vigência, histórico e aprovação independente para mudanças sensíveis.</p></div><button className="select-button" onClick={() => { parameters.refetch(); approvals.refetch(); }}><RotateCcw size={14} /> Atualizar</button></header>
    {message && <div className="settings-message" role="status"><Check size={15} />{message}<button aria-label="Dispensar aviso" onClick={() => setMessage('')}>×</button></div>}
    {parameters.isError && <div className="settings-notice"><AlertTriangle size={16} /><span>Não foi possível carregar os parâmetros. Inicialize os padrões ou confira sua sessão.</span><button className="select-button" onClick={() => seed.mutate()} disabled={seed.isPending}>{seed.isPending ? 'Inicializando...' : 'Carregar padrões'}</button></div>}
    <div className="settings-section-heading"><div><span className="eyebrow">CATÁLOGO VERSIONADO</span><h3>Parâmetros previdenciários e operacionais</h3></div>{parameters.data?.length === 0 && <button className="select-button" onClick={() => seed.mutate()} disabled={seed.isPending}>{seed.isPending ? 'Inicializando...' : 'Carregar padrões'}</button>}</div>
    <div className="parameter-list">{(parameters.data || []).map((parameter) => <ParameterEditor key={parameter.code} parameter={parameter} onSaved={complete} />)}{!parameters.isLoading && !parameters.isError && !parameters.data?.length && <div className="settings-empty">Nenhum parâmetro configurado ainda.</div>}</div>
    <section className="approval-section"><div className="settings-section-heading"><div><span className="eyebrow">SEGUNDO FATOR HUMANO</span><h3>Aprovações pendentes</h3></div><span className="approval-count">{approvals.data?.length || 0}</span></div>
      {approvals.data?.length ? approvals.data.map((approval) => <article className="approval-row" key={approval.id}><div><strong>{approval.resource_key}</strong><p>{approval.reason}</p><small>Solicitado por usuário #{approval.requester_id} · {new Date(approval.created_at).toLocaleString('pt-BR')}</small></div><div className="approval-actions"><button className="approval-reject" onClick={() => review.mutate({ id: approval.id, decision: 'rejeitado' })} disabled={review.isPending}>Rejeitar</button><button className="approval-accept" onClick={() => review.mutate({ id: approval.id, decision: 'aprovado' })} disabled={review.isPending}>Aprovar</button></div></article>) : <div className="settings-empty"><Clock3 size={16} />Nenhuma aprovação aguardando revisão independente.</div>}
    </section>
    <p className="settings-audit-note"><ShieldCheck size={14} /> Alterações sensíveis não são aplicadas até aprovação de outro Super Administrador. Toda versão e decisão fica registrada.</p>
  </section>;
}

function ParameterEditor({ parameter, onSaved }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(JSON.stringify(parameter.value, null, 2));
  const [reason, setReason] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const history = useQuery({ queryKey: ['parameter-history', parameter.code], queryFn: async () => (await api.get(`/configuracoes/parametros/${parameter.code}/historico`)).data, enabled: historyOpen });
  const update = useMutation({
    mutationFn: (payload) => api.put(`/configuracoes/parametros/${parameter.code}`, payload),
    onSuccess: ({ data }) => { onSaved(data); setReason(''); queryClient.invalidateQueries({ queryKey: ['parameter-history', parameter.code] }); },
  });
  const submit = (event) => {
    event.preventDefault();
    let parsed;
    try { parsed = JSON.parse(value); } catch { update.reset(); return; }
    update.mutate({ value: parsed, reason });
  };

  return <article className="parameter-row"><header><div><span className="parameter-category">{parameter.category}</span><h4>{parameter.description}</h4><code>{parameter.code}</code></div><span className="version-badge">v{parameter.version}</span></header>
    <form className="parameter-form" onSubmit={submit}><label><span>VALOR ATUAL</span><textarea aria-label={`Valor do parâmetro ${parameter.code}`} rows={2} value={value} onChange={(event) => setValue(event.target.value)} /></label><label><span>MOTIVO DA ALTERAÇÃO</span><input aria-label={`Motivo da alteração ${parameter.code}`} value={reason} onChange={(event) => setReason(event.target.value)} minLength={8} maxLength={500} required placeholder="Descreva a justificativa" /></label><div className="parameter-actions"><button className="parameter-history-button" type="button" onClick={() => setHistoryOpen(!historyOpen)}><Clock3 size={14} />{historyOpen ? 'Ocultar histórico' : 'Histórico'}</button><button className="parameter-save" type="submit" disabled={update.isPending || !reason.trim()}><Save size={14} />{update.isPending ? 'Salvando...' : parameter.sensitive ? 'Solicitar aprovação' : 'Salvar versão'}</button></div></form>
    {update.isError && <div className="parameter-error" role="alert">{update.error.response?.data?.detail || 'Não foi possível salvar. Verifique o valor e a justificativa.'}</div>}
    {historyOpen && <div className="parameter-history">{history.isLoading ? 'Carregando versões...' : history.data?.map((version) => <div key={version.version}><strong>v{version.version}</strong><code>{JSON.stringify(version.value)}</code><span>{new Date(version.valid_from).toLocaleString('pt-BR')}</span><small>{version.change_reason} · usuário #{version.changed_by}</small></div>)}</div>}
  </article>;
}
