import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../auth/context';
import './Login.css';

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const registering = mode === 'register';

  async function handleSubmit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (registering) {
        await register(username, password);
      }
      await login(username, password);
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode() {
    setMode(registering ? 'login' : 'register');
    setError(null);
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>{registering ? 'Create Account' : 'Welcome Back'}</h1>
          <p>
            {registering
              ? 'Register an account to browse firmware releases.'
              : 'Sign in to manage firmware releases for your devices.'}
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            Username
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label className="login-field">
            Password
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete={registering ? 'new-password' : 'current-password'}
              minLength={registering ? 8 : undefined}
              required
            />
          </label>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-submit" disabled={submitting}>
            {registering ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <p className="login-note">
          {registering ? 'Already have an account? ' : 'New here? '}
          <button type="button" className="login-switch" onClick={switchMode}>
            {registering ? 'Sign in' : 'Create an account'}
          </button>
        </p>

        {registering && (
          <p className="login-note">
            Self-signup creates an operator account; firmware upload stays admin-only.
          </p>
        )}
      </div>
    </div>
  );
}
