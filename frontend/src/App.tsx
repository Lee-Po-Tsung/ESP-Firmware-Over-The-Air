// import { useState } from 'react'
import './App.css'
import { Routes, Route, Link, useLocation } from 'react-router'
import FirmwareList from './pages/FirmwareList';
import FirmwareUpload from './pages/FirmwareUpload';
import Login from './pages/Login';
import { useState, useEffect } from 'react'

function Header({ login }: { login: boolean }) {
  const { pathname } = useLocation();
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
          {login ? (
            <button type="button" className="auth-btn logout-btn">
              Logout
            </button>
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

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  useEffect(() => {
    try {
      fetch("backend/api/user")
        .then(res => res.json())
        .then(json => {
          console.log(json);
          setIsLoggedIn(json["status"] === 1);
        });
    }
    catch (e) {
      console.error("Failed to fetch user info:", e);
    }
  }, []);

  return (
    <>
      <Header login={isLoggedIn} />
      <Routes>
        <Route index element={<FirmwareList />} />
        <Route path="/upload" element={<FirmwareUpload />} />
        <Route path="/login" element={<Login />} />
      </Routes>
    </>
  )
}

export default App
