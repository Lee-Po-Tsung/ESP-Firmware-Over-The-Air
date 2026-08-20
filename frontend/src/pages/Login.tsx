import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../auth/context';
import './Login.css';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(username, password);
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
        <div className="login-logo font-mono text-xs font-bold text-inverse">ESP</div>
        <div className="login-brand-text">
          <div className="login-brand-title text-2xl font-bold text-primary font-mono">ESPFleet</div>
          <div className="login-brand-subtitle text-sm text-secondary font-mono">Firmware releases and fleet status</div>
        </div>
      </div>

      <div className="card login-card">
        <div className="login-header">
          <h1 className="text-xl font-bold text-primary">Sign in</h1>
          <p className="text-sm text-secondary">
            Publish firmware versions and watch every device that has checked in.
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="login-username">Username</label>
            <input
              id="login-username"
              type="text"
              className="form-input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <div className="alert alert-error">
              <span className="alert-title">Sign-in failed: </span>
              {error}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem', padding: '0.8rem' }} disabled={submitting}>
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>

      <p className="login-footer text-xs text-secondary">
        No account? Ask an admin to create one.
      </p>
    </div>
  );
}
