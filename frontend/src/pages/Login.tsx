import { useEffect, useRef } from 'react';
import './Login.css';

function GoogleLoginButton() {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const script = document.createElement('script');
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);
    script.addEventListener('load', () => {
      (window as any).google.accounts.id.initialize({
        client_id: import.meta.env.VITE_GOOGLE_OAUTH_ID,
        ux_mode: 'redirect',
        login_uri: `${import.meta.env.VITE_BACKEND}/api/auth/google`,
      });

      (window as any).google.accounts.id.renderButton(
        divRef.current!,
        {
          type: "standard",
          theme: "outline",
          size: "large"
        }
      );
    })

    return () => {
      document.body.removeChild(script);
    };
  });


  return (
    <div ref={divRef}></div> // fetch google button style fail(403)
  );
}

function GitHubLoginButton() {
  function handleClick() {
    try {
      fetch("/backend/api/auth/github/url").then(res => res.json()).then(json => {
        const url = json["url"];
        if (url === null) throw new Error("Failed to fetch GitHub URL");
        window.location.href = url;
      })
    }
    catch (e) {
      console.error(e)
    }
  }
  return (
    <button type="button" className="social-btn github-btn" aria-label="Sign in with GitHub" onClick={handleClick}>
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
