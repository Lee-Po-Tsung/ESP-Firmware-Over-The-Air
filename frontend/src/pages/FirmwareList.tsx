import React from 'react';
import { Link } from 'react-router';
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

const mockFirmwares: Firmware[] = [
  {
    id: 1,
    model: "esp32-cam",
    version: "v1.0.0",
    filename: "firmware_esp32_cam_v1.0.0.bin",
    signature: "base64encoded_signature_string_here...",
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    created_at: "2023-10-25T14:30:00Z"
  },
  {
    id: 2,
    model: "esp32-wroom-32",
    version: "v1.1.2",
    filename: "firmware_esp32_wroom_v1.1.2.bin",
    signature: "another_base64encoded_signature_string...",
    sha256: "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92",
    created_at: "2023-10-28T09:15:00Z"
  }
];

export default function FirmwareList() {
  return (
    <div className="page-wrapper">
      <div className="main-card">
        <div className="main-card-header">
          <div className="header-titles">
            <h1>Title</h1>
            <p>description...</p>
          </div>
          <Link to="/upload" className="upload-link-btn">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Upload Firmware
          </Link>
        </div>

        <div className="main-card-body">
          <h2 className="section-title">
            Firmwares
          </h2>

          <div className="firmware-stack">
            {mockFirmwares.map(fw => (
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
