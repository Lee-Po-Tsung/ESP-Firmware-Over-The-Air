import './App.css'
import { Routes, Route, Link, Navigate, useLocation } from 'react-router'
import type { ReactNode } from 'react';
import FirmwareList from './pages/FirmwareList';
import FirmwareUpload from './pages/FirmwareUpload';
import Login from './pages/Login';
import { useAuth } from './auth/context';

function Header() {
  const { pathname } = useLocation();
  const { session, logout } = useAuth();
  const showBack = pathname === '/upload' || pathname === '/login';

  return (
    <header className="app-header">
      <div className="header-inner">
        {showBack ? (
          <Link to="/" className="header-back-link">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Dashboard
          </Link>
        ) : (
          <span />
        )}

        <div className="header-auth">
          {session ? (
            <>
              <span className="header-user">
                {session.username}
                <span className="header-role">{session.role}</span>
              </span>
              <button type="button" className="auth-btn logout-btn" onClick={logout}>
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="auth-btn login-btn">
              Login
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

// Upload needs a bearer token, so send visitors through login first.
function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  return session ? children : <Navigate to="/login" replace />;
}

function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route index element={<FirmwareList />} />
        <Route
          path="/upload"
          element={
            <RequireAuth>
              <FirmwareUpload />
            </RequireAuth>
          }
        />
        <Route path="/login" element={<Login />} />
      </Routes>
    </>
  )
}

export default App
