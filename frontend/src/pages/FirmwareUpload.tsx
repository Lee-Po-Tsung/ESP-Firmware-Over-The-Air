import React, { useRef, useState } from 'react';
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
      const res = await fetch('/backend/firmware/upload', {
        method: 'POST',
        body: new FormData(form),
      });

      if (!res.ok) {
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
