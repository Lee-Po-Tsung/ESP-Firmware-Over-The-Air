import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '../auth/context';
import './FirmwareList.css';

interface Firmware {
  id: number;
  model: string;
  version: string;
  filename: string;
  signature: string;
  sha256: string;
  created_at: string;
}

export default function FirmwareList() {
  const { session } = useAuth();
  const [firmwares, setfirmwares] = useState<Firmware[]>([]);

  useEffect(() => {
    if (!session) return;
    fetch('/backend/api/firmware/list', {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(res => {
        if (!res.ok) throw new Error(`Failed to fetch firmwares (HTTP ${res.status})`);
        return res.json() as Promise<Firmware[]>;
      })
      .then(setfirmwares)
      .catch(e => console.error("Failed to fetch firmwares:", e));
  }, [session]);

  return (
    <div className="page-wrapper">
      <div className="main-card">
        <div className="main-card-header">
          <div className="header-titles">
            <h1>Title</h1>
            <p>description...</p>
          </div>
          <div className="header-actions">
            <Link to="/devices" className="devices-link-btn">
              <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Devices
            </Link>
            <Link to="/upload" className="upload-link-btn">
              <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Upload Firmware
            </Link>
          </div>
        </div>

        <div className="main-card-body">
          <h2 className="section-title">
            Firmwares
          </h2>

          <div className="firmware-stack">
            {firmwares.map(fw => (
              <div key={fw.id} className="fw-row-card">
                <div className="fw-row-header">
                  <div className="fw-identity">
                    <h3 className="fw-model">{fw.model}</h3>
                    <span className="fw-badge">{fw.version}</span>
                  </div>
                  <div className="fw-date">
                    Uploaded: {new Date(fw.created_at).toLocaleString()}
                  </div>
                </div>

                <div className="fw-details-grid">
                  <div className="fw-detail-item">
                    <span className="fw-detail-label">File</span>
                    <div className="fw-detail-value">{fw.filename}</div>
                  </div>
                  <div className="fw-detail-item">
                    <span className="fw-detail-label">SHA-256 Hash</span>
                    <div className="fw-detail-value">{fw.sha256}</div>
                  </div>
                  <div className="fw-detail-item">
                    <span className="fw-detail-label">Signature</span>
                    <div className="fw-detail-value">{fw.signature}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
