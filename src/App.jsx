import { useMemo, useState } from 'react';
import { Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, ArrowDownRight, ArrowUpRight, BadgeCheck, Bell, BriefcaseBusiness,
  CalendarDays, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, ClipboardCheck,
  FileClock, FileText, LayoutDashboard, LogOut, Menu, Plus, Search, Settings,
  ShieldCheck, UserRound, Users, X,
} from 'lucide-react';
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import './App.css';
import LoginPage from './pages/LoginPage';
import ProtectedRoute from './components/ProtectedRoute';
import { useAuth } from './contexts/AuthContext';

const pagePaths = {
  'Visão geral': '/dashboard', Segurados: '/segurados', Recenseamento: '/recenseamento',
  Documentos: '/documentos', Monitoramento: '/monitoramento', Relatórios: '/relatorios',
  'Usuários e perfis': '/usuarios',
};

const navigation = [
  { label: 'Visão geral', icon: LayoutDashboard, group: 'GESTÃO' },
  { label: 'Segurados', icon: Users },
  { label: 'Recenseamento', icon: ClipboardCheck },
  { label: 'Documentos', icon: FileText },
  { label: 'Monitoramento', icon: Activity, group: 'CONTROLE' },
  { label: 'Relatórios', icon: FileClock },
  { label: 'Usuários e perfis', icon: ShieldCheck, group: 'SISTEMA' },
];

const chartData = [
  { month: 'Mai', total: 32 }, { month: 'Jun', total: 46 },
  { month: 'Jul', total: 39 }, { month: 'Ago', total: 61 },
  { month: 'Set', total: 53 }, { month: 'Out', total: 78 },
];

const initialInsured = [
  { name: 'Mariana Costa Ferreira', cpf: '***.482.***-09', type: 'Aposentada', status: 'Completo', initials: 'MF', tone: 'rose', date: 'Hoje, 10:42' },
  { name: 'Roberto Almeida Santos', cpf: '***.195.***-31', type: 'Servidor ativo', status: 'Em análise', initials: 'RS', tone: 'blue', date: 'Hoje, 09:18' },
  { name: 'Ana Paula Nascimento', cpf: '***.704.***-62', type: 'Pensionista', status: 'Pendente', initials: 'AN', tone: 'gold', date: 'Ontem, 16:05' },
  { name: 'Carlos Eduardo Ribeiro', cpf: '***.031.***-47', type: 'Servidor ativo', status: 'Completo', initials: 'CR', tone: 'green', date: 'Ontem, 14:32' },
];

const sectionDetails = {
  'Recenseamento': { eyebrow: 'CICLO 2025 · EM ANDAMENTO', title: 'Recenseamento', description: 'Acompanhe a prova de vida e a atualização cadastral dos beneficiários.', metric: '68,4%', metricLabel: 'concluído', rows: [['Aposentados recenseados', '1.284 de 1.760'], ['Pensionistas recenseados', '392 de 610'], ['Pendentes com risco de suspensão', '147 beneficiários']] },
  'Documentos': { eyebrow: 'GESTÃO DOCUMENTAL', title: 'Documentos', description: 'Revise arquivos enviados e acompanhe os itens que precisam de atenção.', metric: '86', metricLabel: 'em análise', rows: [['Aguardando validação', '86 documentos'], ['Próximos do vencimento', '23 documentos'], ['Rejeitados para correção', '12 documentos']] },
  'Monitoramento': { eyebrow: 'AUDITORIA E ACESSOS', title: 'Monitoramento', description: 'Acompanhe acessos ao sistema e alterações cadastrais recentes.', metric: '2', metricLabel: 'alertas hoje', rows: [['Logins bem-sucedidos hoje', '248 acessos'], ['Tentativas de acesso falhas', '7 tentativas'], ['Alterações cadastrais hoje', '34 registros']] },
  'Relatórios': { eyebrow: 'CENTRAL DE RELATÓRIOS', title: 'Relatórios', description: 'Consulte indicadores e prepare exportações para análise.', metric: '6', metricLabel: 'relatórios prontos', rows: [['Segurados por vínculo', 'Atualizado hoje'], ['Recenseamento por campanha', 'Atualizado hoje'], ['Documentos pendentes e vencidos', 'Atualizado ontem']] },
  'Usuários e perfis': { eyebrow: 'ADMINISTRAÇÃO DO SISTEMA', title: 'Usuários e perfis', description: 'Gerencie o acesso da equipe de acordo com suas responsabilidades.', metric: '24', metricLabel: 'usuários ativos', rows: [['Administradores', '3 usuários'], ['Operadores', '16 usuários'], ['Auditores e gestores', '5 usuários']] },
};

function DashboardApp() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const activePage = Object.entries(pagePaths).find(([, path]) => path === location.pathname)?.[0] || 'Visão geral';
  const [query, setQuery] = useState('');
  const [showAll, setShowAll] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const filteredInsured = useMemo(() => initialInsured.filter((person) =>
    `${person.name} ${person.type} ${person.cpf}`.toLowerCase().includes(query.toLowerCase()),
  ), [query]);

  const notify = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(''), 2800);
  };

  const selectPage = (page) => {
    navigate(pagePaths[page] || '/dashboard');
    setMobileNavOpen(false);
  };

  const detail = sectionDetails[activePage];

  return (
    <div className="app-shell">
      {mobileNavOpen && <button className="nav-scrim" aria-label="Fechar menu" onClick={() => setMobileNavOpen(false)} />}
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><span /></div>
          <div className="brand-copy"><strong>aurora</strong><span>PREVIDÊNCIA MUNICIPAL</span></div>
          <button className="icon-button sidebar-close" aria-label="Fechar menu" onClick={() => setMobileNavOpen(false)}><X size={18} /></button>
        </div>
        <div className="institution-switcher">
          <div className="institution-icon"><LandmarkIcon /></div>
          <div><span>INSTITUTO</span><strong>IPM · Santa Aurora</strong></div>
          <ChevronDown size={15} />
        </div>
        <nav className="side-navigation" aria-label="Navegação principal">
          {navigation.map((item) => {
            const Icon = item.icon;
            return <div key={item.label}>
              {item.group && <div className="nav-group-label">{item.group}</div>}
              <button className={`nav-item ${activePage === item.label ? 'nav-item-active' : ''}`} onClick={() => selectPage(item.label)}>
                <Icon size={18} strokeWidth={1.8} /><span>{item.label}</span>
                {item.label === 'Documentos' && <span className="nav-count">12</span>}
              </button>
            </div>;
          })}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => notify('Central de ajuda indisponível no modo de demonstração.')}><CircleHelp size={18} /><span>Central de ajuda</span></button>
          <div className="sidebar-profile">
            <div className="profile-avatar">LC</div>
            <div className="profile-copy"><strong>{user?.full_name || 'Usuário'}</strong><span>{user?.profiles?.[0] || 'Equipe'}</span></div>
            <button className="icon-button profile-menu" aria-label="Sair do sistema" title="Sair" onClick={() => logout()}><LogOut size={15} /></button>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Abrir menu" onClick={() => setMobileNavOpen(true)}><Menu size={21} /></button>
          <div className="breadcrumbs"><span>Início</span><ChevronRight size={14} /><strong>{activePage}</strong></div>
          <div className="topbar-actions">
            <label className="global-search"><Search size={16} /><input aria-label="Buscar no sistema" placeholder="Buscar segurado, CPF..." onKeyDown={(event) => { if (event.key === 'Enter') { setQuery(event.currentTarget.value); selectPage('Segurados'); } }} /><kbd>⌘ K</kbd></label>
            <button className="icon-button notification-button" aria-label="Notificações" onClick={() => notify('Você está em dia com as notificações.')}><Bell size={18} /><span /></button>
            <div className="topbar-divider" />
            <button className="topbar-user" onClick={() => selectPage('Usuários e perfis')}><span className="topbar-avatar">LC</span><span className="topbar-user-name">Larissa Carvalho</span><ChevronDown size={15} /></button>
          </div>
        </header>

        <div className="page-content">
          <div className="demo-banner"><span className="demo-dot" /> AMBIENTE DE DEMONSTRAÇÃO <span>·</span> Dados ilustrativos, sem conexão com cadastro real.</div>
          {activePage === 'Visão geral' ? <>
            <section className="welcome-row">
              <div><div className="eyebrow"><CalendarDays size={14} /> {new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(new Date()).toUpperCase()}</div><h1>Olá, {user?.full_name?.split(' ')[0] || 'equipe'} <span>☀</span></h1><p>Aqui está o panorama da previdência municipal hoje.</p></div>
              <button className="primary-button" onClick={() => selectPage('Segurados')}><Plus size={17} /> Novo segurado</button>
            </section>

            <section className="metrics-grid" aria-label="Indicadores principais">
              <MetricCard label="Total de segurados" value="8.246" change="4,8%" note="vs. mês anterior" icon={Users} tone="sage" direction="up" />
              <MetricCard label="Servidores ativos" value="5.104" change="2,1%" note="vs. mês anterior" icon={BriefcaseBusiness} tone="blue" direction="up" />
              <MetricCard label="Aposentados" value="2.318" change="1,3%" note="vs. mês anterior" icon={UserRound} tone="lavender" direction="up" />
              <MetricCard label="Pensionistas" value="824" change="0,6%" note="vs. mês anterior" icon={BadgeCheck} tone="amber" direction="down" />
            </section>

            <section className="overview-grid">
              <div className="panel registration-panel">
                <div className="panel-heading"><div><div className="eyebrow">MOVIMENTAÇÃO</div><h2>Cadastros ao longo do tempo</h2></div><button className="select-button" onClick={() => notify('Período selecionado: últimos 6 meses')}>Últimos 6 meses <ChevronDown size={14} /></button></div>
                <div className="chart-legend"><span><i /> Novos cadastros</span><strong>309 <small>este mês</small></strong></div>
                <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 10, right: 4, left: -22, bottom: 0 }}><defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#527b68" stopOpacity={0.19} /><stop offset="95%" stopColor="#527b68" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#edf0eb" /><XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#8a918a', fontSize: 12 }} dy={10} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#8a918a', fontSize: 11 }} /><Tooltip contentStyle={{ border: '1px solid #e8ebe6', borderRadius: 8, fontSize: 12 }} /><Area type="monotone" dataKey="total" stroke="#527b68" strokeWidth={2.5} fill="url(#chartFill)" activeDot={{ r: 5, fill: '#527b68', stroke: '#fff', strokeWidth: 2 }} /></AreaChart></ResponsiveContainer></div>
                <div className="chart-footnote"><span><i className="trend-up"><ArrowUpRight size={13} /></i> 12,6% <span>vs. período anterior</span></span><button className="text-button" onClick={() => selectPage('Relatórios')}>Ver relatório <ArrowUpRight size={14} /></button></div>
              </div>
              <div className="panel census-panel">
                <div className="panel-heading"><div><div className="eyebrow">CAMPANHA ATIVA</div><h2>Recenseamento 2025</h2></div><button className="more-button" aria-label="Mais opções" onClick={() => notify('Opções da campanha')}>···</button></div>
                <div className="census-total"><strong>68,4<span>%</span></strong><span className="census-target">Meta: 100%</span></div>
                <div className="progress-track"><span style={{ width: '68.4%' }} /></div>
                <div className="progress-labels"><span>1.676 realizados</span><span>2.450 no total</span></div>
                <div className="census-divider" />
                <div className="census-breakdown"><div><span className="breakdown-dot dot-active" /><span>Aposentados</span><strong>73,0%</strong></div><div><span className="breakdown-dot dot-pension" /><span>Pensionistas</span><strong>55,8%</strong></div></div>
                <button className="panel-link" onClick={() => selectPage('Recenseamento')}>Acompanhar campanha <ArrowUpRight size={15} /></button>
              </div>
            </section>

            <section className="bottom-grid">
              <div className="panel table-panel">
                <div className="panel-heading table-heading"><div><div className="eyebrow">ATIVIDADE RECENTE</div><h2>Últimos cadastros</h2></div><button className="text-button" onClick={() => { setShowAll(!showAll); selectPage('Segurados'); }}>{showAll ? 'Recolher' : 'Ver todos'} <ArrowUpRight size={14} /></button></div>
                <div className="table-scroll"><table><thead><tr><th>SEGURADO</th><th>VÍNCULO</th><th>STATUS</th><th>ATUALIZADO</th><th /></tr></thead><tbody>{initialInsured.slice(0, 3).map((person) => <InsuredRow key={person.name} person={person} onClick={() => notify(`Cadastro demonstrativo de ${person.name}`)} />)}</tbody></table></div>
              </div>
              <div className="panel attention-panel">
                <div className="panel-heading"><div><div className="eyebrow">PRECISAM DE ATENÇÃO</div><h2>Pendências</h2></div><span className="attention-total">3</span></div>
                <button className="attention-item" onClick={() => selectPage('Documentos')}><span className="attention-icon document-attention"><FileText size={17} /></span><span><strong>Documentos para análise</strong><small>12 aguardando validação</small></span><ChevronRight size={16} /></button>
                <button className="attention-item" onClick={() => selectPage('Recenseamento')}><span className="attention-icon census-attention"><ClipboardCheck size={17} /></span><span><strong>Recenseamento pendente</strong><small>147 com prazo próximo</small></span><ChevronRight size={16} /></button>
                <button className="attention-item" onClick={() => selectPage('Segurados')}><span className="attention-icon profile-attention"><UserRound size={17} /></span><span><strong>Cadastros incompletos</strong><small>28 precisam de atualização</small></span><ChevronRight size={16} /></button>
              </div>
            </section>
          </> : activePage === 'Segurados' ? <>
            <section className="welcome-row section-welcome"><div><div className="eyebrow">BASE PREVIDENCIÁRIA</div><h1>Segurados</h1><p>Consulte e acompanhe os cadastros do instituto.</p></div><button className="primary-button" onClick={() => notify('O formulário de cadastro estará disponível com a API.')}><Plus size={17} /> Novo segurado</button></section>
            <section className="panel insured-list-panel"><div className="insured-toolbar"><label className="list-search"><Search size={16} /><input aria-label="Buscar segurados" placeholder="Nome, CPF ou matrícula" value={query} onChange={(event) => setQuery(event.target.value)} /></label><button className="select-button" onClick={() => notify('Filtros de vínculo')}>Todos os vínculos <ChevronDown size={14} /></button><button className="select-button" onClick={() => notify('Filtros de situação')}>Situação <ChevronDown size={14} /></button></div><div className="table-scroll"><table><thead><tr><th>SEGURADO</th><th>VÍNCULO</th><th>STATUS</th><th>ATUALIZADO</th><th /></tr></thead><tbody>{(showAll ? filteredInsured : filteredInsured.slice(0, 4)).map((person) => <InsuredRow key={person.name} person={person} onClick={() => notify(`Cadastro demonstrativo de ${person.name}`)} />)}</tbody></table></div><div className="list-footer"><span>Exibindo {filteredInsured.length} segurados demonstrativos</span><div><button className="icon-button" aria-label="Página anterior" onClick={() => notify('Esta é a primeira página')}><ChevronLeft size={17} /></button><span className="page-number">1</span><button className="icon-button" aria-label="Próxima página" onClick={() => notify('Não há mais resultados demonstrativos')}><ChevronRight size={17} /></button></div></div></section>
          </> : <>
            <section className="welcome-row section-welcome"><div><div className="eyebrow">{detail?.eyebrow || 'ÁREA DO SISTEMA'}</div><h1>{detail?.title || activePage}</h1><p>{detail?.description || 'Consulte e gerencie as informações do instituto.'}</p></div><button className="select-button" onClick={() => notify('Filtros disponíveis após integração com a API')}><Settings size={15} /> Opções</button></section>
            <section className="module-summary"><div className="panel module-metric"><span>{detail?.metricLabel}</span><strong>{detail?.metric}</strong><small><ArrowUpRight size={14} /> atualizado agora</small></div><div className="panel module-items"><div className="eyebrow">RESUMO</div>{detail?.rows.map(([label, value]) => <div className="module-row" key={label}><span>{label}</span><strong>{value}</strong><ChevronRight size={16} /></div>)}</div></section>
          </>}
          <footer className="page-footer"><span>IPM Santa Aurora · Sistema de Gestão Previdenciária</span><span>Versão de demonstração <i /> Seguro e auditável</span></footer>
        </div>
      </main>
      {notice && <div className="toast" role="status"><BadgeCheck size={17} />{notice}<button className="icon-button" aria-label="Dispensar aviso" onClick={() => setNotice('')}><X size={15} /></button></div>}
    </div>
  );
}

function MetricCard({ label, value, change, note, icon: Icon, tone, direction }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={18} strokeWidth={1.8} /></span></div><div className="metric-value">{value}</div><div className="metric-foot"><span className="metric-change"><i className={direction === 'up' ? '' : 'change-down'}>{direction === 'up' ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}</i>{change}</span><span>{note}</span></div></article>;
}

function InsuredRow({ person, onClick }) {
  return <tr onClick={onClick} tabIndex="0" onKeyDown={(event) => { if (event.key === 'Enter') onClick(); }}><td><div className="insured-name-cell"><span className={`person-avatar ${person.tone}`}>{person.initials}</span><span><strong>{person.name}</strong><small>{person.cpf}</small></span></div></td><td>{person.type}</td><td><span className={`status-pill status-${person.status === 'Completo' ? 'complete' : person.status === 'Em análise' ? 'review' : 'pending'}`}><i />{person.status}</span></td><td>{person.date}</td><td><button className="row-more" aria-label={`Opções para ${person.name}`} onClick={(event) => { event.stopPropagation(); onClick(); }}>···</button></td></tr>;
}

function LandmarkIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 9 9-5 9 5M5 10v8m4-8v8m6-8v8m4-8v8M3 20h18M2 22h20" /></svg>;
}

export default function App() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="*" element={<ProtectedRoute><DashboardApp /></ProtectedRoute>} />
  </Routes>;
}
