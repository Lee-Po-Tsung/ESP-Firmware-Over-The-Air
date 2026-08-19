import React, { useRef, useState } from 'react';
import { useAuth } from '../auth/context';
import './FirmwareUpload.css';

export default function FirmwareUpload() {
  const { session } = useAuth();
  const formRef = useRef<HTMLFormElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>('');

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
        headers: session ? { Authorization: `Bearer ${session.token}` } : undefined,
        body: new FormData(form),
      });

      if (res.status === 401) {
        setMessage('Session expired. Please log in again.');
        return;
      }
      if (res.status === 403) {
        setMessage('Only admin accounts can upload firmware.');
        return;
      }
      // Several distinct causes share these codes, and the backend already
      // names which one in `detail`, so show it rather than mirroring the list.
      if (res.status === 400 || res.status === 409) {
        const body = await res.json().catch(() => null);
        setMessage(body?.detail ?? `Upload failed (HTTP ${res.status})`);
        return;
      }
      if (!res.ok) {
        setMessage(`Upload failed (HTTP ${res.status})`);
        return;
      }

      setMessage('Firmware uploaded successfully.');
      form.reset();
      setSelectedFileName('');
    } catch {
      setMessage('Cannot reach backend. Please make sure API server is running on port 1234.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="upload-container">
      <div className="card upload-card">
        <div className="upload-header">
          <h1 className="text-xl font-bold text-primary">Publish firmware</h1>
          <p className="text-xs text-secondary">The server signs the image on upload. Devices of this model are offered it on their next check.</p>
        </div>
        <form ref={formRef} onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="firmware-file">Firmware image (.bin)</label>
            <div className="dropzone">
              <input
                id="firmware-file"
                type="file"
                name="firmware"
                className="dropzone-input"
                accept=".bin"
                required
                onChange={event => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFileName(file ? file.name : '');
                }}
              />
              <div className="dropzone-content">
                <span className="btn btn-secondary">
                  + Choose a .bin file
                </span>
                {selectedFileName
                  ? <span className="form-help font-mono">{selectedFileName}</span>
                  : <span className="form-help">or drop one here</span>}
              </div>
            </div>
          </div>

          {/* Free text, not a list. `model` is whatever string the device sends
              in `POST /api/check`, so a fixed list here is a second source of
              truth that silently blocks any board not on it. */}
          <div className="form-group">
            <label className="form-label" htmlFor="firmware-model">Device model</label>
            <input id="firmware-model" type="text" className="form-input" name="model" placeholder="ESP32-S3-DevKit" required />
            <span className="form-help">Must match FIRMWARE_MODEL in the sketch, exactly.</span>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="firmware-version">Version</label>
            <input id="firmware-version" type="text" className="form-input" name="version" placeholder="2.4.2" required />
            <span className="form-help">Three numeric segments: major.minor.patch</span>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="firmware-notes">Release notes</label>
            <textarea
              id="firmware-notes"
              name="notes"
              className="form-input"
              rows={4}
              placeholder="What changed in this version?"
              style={{ resize: 'vertical' }}
            />
          </div>

          {message && (
            <div className={`alert ${message.includes('success') ? 'alert-info' : 'alert-error'}`}>
              {message}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.9rem', padding: '0.82rem' }} disabled={submitting}>
            {submitting ? 'Uploading...' : 'Upload and publish'}
          </button>
        </form>
      </div>
    </div>
  );
}
