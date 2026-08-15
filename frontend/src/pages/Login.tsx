import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../auth/context';
import './Login.css';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(email, password);
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-brand">
        <div className="login-logo">ESP</div>
        <div className="login-brand-text">
          <div className="login-brand-title">ESPFleet</div>
          <div className="login-brand-subtitle">韌體發佈與裝置監控</div>
        </div>
      </div>

      <div className="login-card">
        <div className="login-header">
          <h1>登入控制台</h1>
          <p>
            用你的工作帳號登入，即可管理韌體版本並查看所有裝置的即時狀態。
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            電子郵件
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label className="login-field">
            密碼
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <div className="login-form-actions">
            <label className="login-remember">
              <input
                type="checkbox"
                checked={remember}
                onChange={e => setRemember(e.target.checked)}
              />
              記住這台電腦
            </label>
            <a href="#" className="login-forgot">忘記密碼？</a>
          </div>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-submit" disabled={submitting}>
            登入
          </button>
        </form>
      </div>

      <p className="login-footer">
        還沒有帳號？請聯絡你的組織管理員。
      </p>
    </div>
  );
}
