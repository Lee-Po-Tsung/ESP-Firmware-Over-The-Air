import { useState, useEffect } from 'react';
import { useAuth } from '../auth/context';
import './DeviceList.css';

// One row per ESP32 unit, fed by the check-ins POST /api/check records.
interface Device {
  id: number;
  device_id: string;
  model: string;
  current_version: string | null;
  last_seen: string | null;
}

// Compact "how long ago" for scanning the fleet; the exact timestamp sits in
// the cell tooltip.
function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.floor(hours / 24)} d ago`;
}

export default function DeviceList() {
  const { session } = useAuth();
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    fetch('/backend/api/devices', {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => {
        if (!res.ok) throw new Error(`Failed to fetch devices (HTTP ${res.status})`);
        return res.json() as Promise<Device[]>;
      })
      .then(setDevices)
      .catch(e => setError(e instanceof Error ? e.message : String(e)));
  }, [session]);

  return (
    <div className="dev-page-wrapper">
      <div className="dev-main-card">
        <div className="dev-card-header">
          <div className="dev-header-titles">
            <h1>Devices</h1>
            <p>Every unit that has checked in, with its firmware version and last contact.</p>
          </div>
        </div>

        <div className="dev-card-body">
          {error && <div className="dev-error">{error}</div>}

          {!error && devices.length === 0 && (
            <div className="dev-empty">No devices have checked in yet.</div>
          )}

          {devices.length > 0 && (
            <table className="dev-table">
              <thead>
                <tr>
                  <th>Device ID</th>
                  <th>Model</th>
                  <th>Version</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {devices.map(d => (
                  <tr key={d.id}>
                    <td className="dev-id">{d.device_id}</td>
                    <td>{d.model}</td>
                    <td>
                      {d.current_version
                        ? <span className="dev-badge">{d.current_version}</span>
                        : <span className="dev-muted">unknown</span>}
                    </td>
                    <td title={d.last_seen ? new Date(d.last_seen).toLocaleString() : undefined}>
                      {d.last_seen
                        ? timeAgo(d.last_seen)
                        : <span className="dev-muted">never</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
