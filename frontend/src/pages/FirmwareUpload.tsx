import React, { useState } from 'react';
import { Link } from 'react-router';
import './FirmwareUpload.css';

export default function FirmwareUpload() {
  const [model, setModel] = useState('');
  const [version, setVersion] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    alert(`Mock Upload:\nModel: ${model}\nVersion: ${version}\nFile: ${file?.name}`);
  };

  return (
    <div className="upload-container">
      <div className="upload-nav">
        <Link to="/" className="back-link">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Dashboard
        </Link>
      </div>

      <div className="upload-header">
        <h1>Upload Firmware</h1>
        <br />
        <p>Deploy a new version to your devices.</p>
      </div>

      <div className="upload-card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Device Model</label>
            <input
              type="text"
              placeholder="hint"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Firmware Version</label>
            <input
              type="text"
              placeholder="hint"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Firmware Binary (.bin)</label>
            <div className="file-input-wrapper">
              <input
                type="file"
                className="simple-file-input"
                accept=".bin"
                onChange={handleFileChange}
                required
              />
            </div>
            <span className="help-text">Only compiled .bin files are accepted.</span>
          </div>

          <button type="submit" className="submit-btn">
            Upload & Sign Firmware
          </button>
        </form>
      </div>
    </div>
  );
}
