import './App.css'
import { Routes, Route, Link, Navigate, useLocation } from 'react-router'
import type { ReactNode } from 'react';
import DeviceList from './pages/DeviceList';
import Firmware from './pages/Firmware';
import Login from './pages/Login';
import { useAuth } from './auth/context';
import { useState, useEffect } from 'react';

function SiderBar() {
  const { pathname } = useLocation();
  const { session, logout } = useAuth();
  const [isCollapsed, setIsCollapsed] = useState(() => window.innerWidth < 960);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 960px)');
    const handleMediaChange = (e: MediaQueryListEvent) => {
      setIsCollapsed(e.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleMediaChange);
    } else {
      mediaQuery.addListener(handleMediaChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleMediaChange);
      } else {
        mediaQuery.removeListener(handleMediaChange);
      }
    };
  }, []);

  if (pathname === '/login') return null;

  const navItems = [
    { to: '/', index: '01', label: 'Firmware', hint: 'Publish and retire versions' },
    { to: '/devices', index: '02', label: 'Devices', hint: 'Connected ESP32 fleet' },
  ];

  function isActivePath(target: string) {
    if (target === '/') return pathname === '/';
    return pathname === target;
  }

  return (
    <>
      {!isCollapsed && <div className="sidebar-backdrop" onClick={() => setIsCollapsed(true)} />}
      <aside className={`sidebar ${isCollapsed ? 'is-collapsed' : ''}`}>
        <div className="sidebar-inner">
          <div className="sidebar-brand">
            <div className="sidebar-mark font-mono text-xs font-bold text-inverse" aria-hidden="true">ESP</div>
            <div className="sidebar-brand-copy">
              <span className="sidebar-title text-base font-medium text-primary font-mono">ESPFleet</span>
              <span className="sidebar-subtitle">Firmware OTA Control Center</span>
            </div>
          </div>

          <nav className="sidebar-nav" aria-label="Primary navigation">
            {navItems.map(item => (
              <Link
                key={item.to}
                to={item.to}
                className={`sidebar-link${isActivePath(item.to) ? ' is-active' : ''}`}
              >
                <span className="sidebar-link-index text-xs font-medium text-primary font-mono">{item.index}</span>
                <span className="sidebar-link-copy">
                  <span className="sidebar-link-label text-sm font-medium font-mono">{item.label}</span>
                  <span className="sidebar-link-hint">{item.hint}</span>
                </span>
              </Link>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-account">
              {session ? (
                <>
                  <strong className="sidebar-account-name text-sm font-medium text-primary font-mono">{session.username}</strong>
                  <span className="sidebar-account-role text-xs text-tertiary font-mono">{session.role}</span>
                </>
              ) : (
                <span className="sidebar-account-name text-sm font-medium text-primary font-mono">Guest</span>
              )}
            </div>

            <div className="sidebar-actions">
              {session ? (
                <button type="button" className="sidebar-action sidebar-logout text-lg font-medium text-primary font-mono" onClick={logout}>
                  <span>Log out</span>
                </button>
              ) : (
                <Link to="/login" className="sidebar-action sidebar-login text-lg font-medium text-primary font-mono">
                  Login
                </Link>
              )}
            </div>
          </div>
        </div>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? "Expand menu" : "Collapse menu"}
        >
          {isCollapsed ? ">" : "<"}
        </button>
      </aside>
    </>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  return session ? children : <Navigate to="/login" replace />;
}

function App() {
  return (
    <>
      <SiderBar />
      <main className="content-shell">
        <Routes>
          <Route
            index
            element={
              <RequireAuth>
                <Firmware />
              </RequireAuth>
            }
          />
          <Route
            path="/upload"
            element={
              <RequireAuth>
                <Navigate to='/' replace />
              </RequireAuth>
            }
          />
          <Route
            path="/devices"
            element={
              <RequireAuth>
                <DeviceList />
              </RequireAuth>
            }
          />
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
    </>
  )
}

export default App
