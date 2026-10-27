import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="route-loading" role="status">Verificando sessao...</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (roles?.length && !user.profiles?.some((role) => roles.includes(role))) {
    return <main className="route-denied"><h1>Acesso nao autorizado</h1><p>Seu perfil nao tem permissao para esta area.</p></main>;
  }
  return children;
}
