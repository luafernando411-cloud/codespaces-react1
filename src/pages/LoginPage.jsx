import { useState } from 'react';
import { ArrowRight, KeyRound, Landmark, ShieldCheck } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [cpf, setCpf] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(cpf, password);
      navigate(location.state?.from?.pathname || '/dashboard', { replace: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Nao foi possivel entrar. Confira sua conexao e tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  return <main className="login-page">
    <section className="login-aside">
      <div className="login-brand"><span className="login-brand-mark"><Landmark size={21} /></span><span><strong>aurora</strong><small>PREVIDENCIA MUNICIPAL</small></span></div>
      <div className="login-aside-copy"><div className="login-overline">IPM · SANTA AURORA</div><h1>Cuidar de quem dedicou a vida ao serviço público.</h1><p>Gestão previdenciária com responsabilidade, transparência e respeito às pessoas.</p></div>
      <div className="login-aside-footer"><ShieldCheck size={16} /> Ambiente institucional protegido</div>
    </section>
    <section className="login-main">
      <div className="login-form-wrap"><div className="login-mobile-brand"><Landmark size={20} /><span>aurora</span></div><div className="login-heading"><span className="login-icon"><KeyRound size={18} /></span><div className="eyebrow">ACESSO AO SISTEMA</div><h2>Bem-vinda de volta</h2><p>Entre com seu CPF e senha institucional.</p></div>
        <form className="login-form" onSubmit={submit}>
          <label htmlFor="login-cpf">CPF</label><input id="login-cpf" name="cpf" autoComplete="username" inputMode="numeric" placeholder="000.000.000-00" value={cpf} onChange={(event) => setCpf(event.target.value)} required minLength={11} />
          <div className="password-label"><label htmlFor="login-password">Senha</label></div><input id="login-password" name="password" type="password" autoComplete="current-password" placeholder="Digite sua senha" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit" disabled={submitting}>{submitting ? 'Entrando...' : 'Entrar'} <ArrowRight size={17} /></button>
        </form>
        <p className="login-security"><ShieldCheck size={14} /> Seus dados sao protegidos e auditados.</p>
      </div>
      <footer className="login-footer">IPM Santa Aurora <span>·</span> Sistema de Gestão Previdenciária</footer>
    </section>
  </main>;
}
