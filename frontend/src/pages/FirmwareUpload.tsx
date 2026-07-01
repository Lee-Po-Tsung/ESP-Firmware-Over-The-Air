import React, { useRef, useState } from 'react';
import { Link } from 'react-router';
import './FirmwareUpload.css';

export default function FirmwareUpload() {
  const formRef = useRef<HTMLFormElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    const form = formRef.current;
    if (!form || !form.reportValidity()) {
      return;
    }

    setSubmitting(true);
    setMessage(null);

    try {
      const res = await fetch('/api/firmware/upload', {
        method: 'POST',
        body: new FormData(form),
      });

      if (!res.ok && res.status !== 303) {
        setMessage(`Upload failed (HTTP ${res.status})`);
        return;
      }

      setMessage('Firmware uploaded successfully.');
      form.reset();
    } catch {
      setMessage('Cannot reach backend. Please make sure API server is running on port 1234.');
    } finally {
      setSubmitting(false);
    }
  }

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
        <form ref={formRef} onSubmit={handleSubmit}>
          <div className="form-group">
            <label>
              Device Model
              <input type="text" name="model" placeholder="hint" required />
            </label>
          </div>

          <div className="form-group">
            <label>
              Firmware Version
              <input type="text" name="version" placeholder="hint" required />
            </label>
          </div>

          <div className="form-group">
            <label>
              Admin Key
              <input type="password" name="admin_key" placeholder="hint" required />
            </label>
          </div>

          <div className="form-group">
            <label>
              Firmware Binary (.bin)
              <div className="file-input-wrapper">
                <input
                  type="file"
                  name="firmware"
                  className="simple-file-input"
                  accept=".bin"
                  required
                  />
              </div>
              <span className="help-text">Only compiled .bin files are accepted.</span>
            </label>
          </div>

          {message && <p className="help-text">{message}</p>}

          <button type="submit" className="submit-btn" disabled={submitting}>
            Upload & Sign Firmware
          </button>
        </form>
      </div>
    </div>
  );
}
