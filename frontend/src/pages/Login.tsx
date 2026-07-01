import './Login.css';

function GoogleLoginButton() {
    return (
        <button type="button" className="social-btn google-btn" aria-label="Sign in with Google">
            <span className="social-icon" aria-hidden="true">
              G
            </span>
            Continue with Google
          </button>
    );
}

function GitHubLoginButton() {
    return (
        <button type="button" className="social-btn github-btn" aria-label="Sign in with GitHub">
            <span className="social-icon" aria-hidden="true">
              GH
            </span>
            Continue with GitHub
          </button>
    );
}

export default function Login() {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>Welcome Back</h1>
          <p>Sign in to manage firmware releases for your devices.</p>
        </div>

        <div className="login-actions">
            <GoogleLoginButton />
            <GitHubLoginButton />
        </div>

        <p className="login-note">Authentication wiring will be added later.</p>
      </div>
    </div>
  );
}
