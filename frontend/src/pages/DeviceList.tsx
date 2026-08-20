import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../auth/context';
import { pickLatestActive } from '../version';
import './DeviceList.css';

interface ApiDevice {
  id: number;
  device_id: string;
  model: string;
  current_version: string | null;
  last_seen: string | null;
}

interface Firmware {
  id: number;
  model: string;
  version: string;
  active: boolean;
  created_at: string;
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'never';
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function getStatus(iso: string | null): 'online' | 'offline' {
  if (!iso) return 'offline';
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  return seconds <= 60 ? 'online' : 'offline';
}



export default function DeviceList() {
  const { session } = useAuth();
  const [apiDevices, setApiDevices] = useState<ApiDevice[]>([]);
  const [firmwares, setFirmwares] = useState<Firmware[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [time, setTime] = useState(new Date().toLocaleTimeString('zh-TW', { hour12: false }));

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState<'all' | 'online' | 'offline'>('all');

  useEffect(() => {
    if (!session) return;
    const fetchData = () => {
      Promise.all([
        fetch('/backend/api/devices', { headers: { Authorization: `Bearer ${session.token}` } }).then(r => {
          if (!r.ok) throw new Error('Failed to fetch devices');
          return r.json();
        }),
        fetch('/backend/api/firmware/list', { headers: { Authorization: `Bearer ${session.token}` } }).then(r => {
          if (!r.ok) throw new Error('Failed to fetch firmwares');
          return r.json();
        })
      ])
        .then(([devs, fws]) => {
          setApiDevices(devs);
          setFirmwares(fws);
          setError(null);
        })
        .catch(e => setError(e instanceof Error ? e.message : String(e)));
    };

    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [session]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString('en-GB', { hour12: false }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // What the server would answer this model's devices, not what was uploaded
  // last. Withdrawn rows are excluded and versions compare as tuples, so a
  // hotfix on an older line does not mark the whole fleet outdated.
  const latestFirmwares = useMemo(() => {
    const byModel = new Map<string, Firmware[]>();
    for (const fw of firmwares) {
      byModel.set(fw.model, [...(byModel.get(fw.model) ?? []), fw]);
    }

    const latest: Record<string, Firmware> = {};
    for (const [model, items] of byModel) {
      const winner = pickLatestActive(items);
      if (winner) latest[model] = winner;
    }
    return latest;
  }, [firmwares]);

  const devices = apiDevices.map(d => {
    const latestFw = latestFirmwares[d.model];
    const is_latest = (latestFw && d.current_version) ? (d.current_version === latestFw.version) : true;

    return {
      id: d.device_id,
      model: d.model,
      current_version: d.current_version || 'unknown',
      is_latest,
      last_seen: timeAgo(d.last_seen),
      status: getStatus(d.last_seen) as 'online' | 'offline' | 'updating'
    };
  });

  const onlineCount = devices.filter(d => d.status === 'online').length;
  const offlineCount = devices.filter(d => d.status === 'offline').length;
  const updatingCount = devices.filter(d => d.status === 'updating').length;
  const outdatedDevices = devices.filter(d => !d.is_latest);
  const uniqueModels = Array.from(new Set([
    ...devices.map(d => d.model),
    ...firmwares.map(f => f.model),
  ])).sort();

  const filteredDevices = devices.filter(d => {
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch = !searchQuery ||
      d.id.toLowerCase().includes(searchLower) ||
      d.model.toLowerCase().includes(searchLower);

    const matchesModel = selectedModel === 'all' || d.model === selectedModel;
    const matchesStatus = selectedStatus === 'all' || d.status === selectedStatus;

    return matchesSearch && matchesModel && matchesStatus;
  });

  return (
    <div className="dev-page">
      <div className="dev-header-area">
        <div className="dev-header-left">
          <h1 className="text-2xl font-bold text-primary">Devices</h1>
        </div>
        <div className="dev-live-indicator font-mono text-xs text-secondary">
          <span className="live-dot"></span>
          Live · {time}
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span className="alert-title">Could not load: </span>
          {error}
        </div>
      )}

      <div className="dev-summary-cards">
        <div className="card dev-card">
          <div className="dev-card-title text-xs text-secondary font-medium">Online</div>
          <div className="dev-card-value text-3xl font-medium font-mono text-success">{onlineCount}</div>
          <div className="dev-card-desc text-xs text-tertiary">Checked in recently</div>
        </div>
        <div className="card dev-card">
          <div className="dev-card-title text-xs text-secondary font-medium">Offline</div>
          <div className="dev-card-value text-3xl font-medium font-mono text-error">{offlineCount}</div>
          <div className="dev-card-desc text-xs text-tertiary">Silent for over 60s</div>
        </div>
        <div className="card dev-card">
          <div className="dev-card-title text-xs text-secondary font-medium">Updating</div>
          <div className="dev-card-value text-3xl font-medium font-mono text-info">{updatingCount}</div>
          <div className="dev-card-desc text-xs text-tertiary">Writing firmware</div>
        </div>
        <div className="card dev-card">
          <div className="dev-card-title text-xs text-secondary font-medium">Outdated</div>
          <div className="dev-card-value text-3xl font-medium font-mono text-primary">{outdatedDevices.length}</div>
          <div className="dev-card-desc text-xs text-tertiary">Updates on next check</div>
        </div>
      </div>

      {outdatedDevices.length > 0 && (
        <div className="alert alert-warning">
          <span className="alert-title">Outdated firmware: </span>
          {outdatedDevices.length} device(s) are not on the latest version: {outdatedDevices.map(d => d.id).join(', ')}. Each updates on its next check-in; an offline one has to come back first.
        </div>
      )}

      <div className="data-table-container dev-table-container">
        <div className="data-table-toolbar dev-table-toolbar">
          <div className="search-box">
            <span className="search-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 -960 960 960" width="18px" fill="currentColor">
                <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z" />
              </svg>
            </span>
            <input
              type="text"
              className="form-input"
              placeholder="Search by name or model"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="dev-table-filters">
            <div className="form-group dev-filter-group">
              <span className="form-label">Model</span>
              <select
                className="form-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                <option value="all">All models</option>
                {uniqueModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
            <div className="form-group dev-filter-group">
              <span className="form-label">Status</span>
              <div className="segmented-control">
                <button
                  className={`segmented-btn ${selectedStatus === 'all' ? 'active' : ''}`}
                  onClick={() => setSelectedStatus('all')}
                >All</button>
                <button
                  className={`segmented-btn ${selectedStatus === 'online' ? 'active' : ''}`}
                  onClick={() => setSelectedStatus('online')}
                >Online</button>
                <button
                  className={`segmented-btn ${selectedStatus === 'offline' ? 'active' : ''}`}
                  onClick={() => setSelectedStatus('offline')}
                >Offline</button>
              </div>
            </div>
          </div>
        </div>

        <div className="dev-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Device</th>
                <th>Firmware</th>
                <th>Last seen</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredDevices.map(d => (
                <tr key={d.id}>
                  <td className="dev-col-device">
                    <div className="dev-device-info">
                      <span className={`dev-status-dot ${d.status === 'online' ? 'dot-green' : 'dot-red'}`}></span>
                      <div className="dev-device-text">
                        <div className="dev-device-name font-mono text-sm font-semibold text-primary">{d.id}</div>
                        <div className="dev-device-meta font-mono text-xs text-tertiary">{d.model}</div>
                      </div>
                    </div>
                  </td>
                  <td className="dev-col-fw">
                    <span className="dev-fw-text font-mono text-sm text-primary">{d.current_version}</span>
                  </td>
                  <td className="dev-col-seen font-mono text-sm text-secondary">
                    {d.last_seen}
                  </td>
                  <td className="dev-col-status">
                    {d.status === 'online' ? (
                      <span className="badge badge-success">Online</span>
                    ) : (
                      <span className="badge badge-error">Offline</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
