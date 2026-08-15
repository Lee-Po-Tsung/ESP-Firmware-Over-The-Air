import React, { useRef, useState } from 'react';
import { useAuth } from '../auth/context';
import './FirmwareUpload.css';

export default function FirmwareUpload() {
  const { session } = useAuth();
  const formRef = useRef<HTMLFormElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>('');
  console.log(selectedFileName); // temp ignore elint

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

      <div className="upload-card">
        <div className="upload-header">
          <h1>上傳新韌體</h1>
          <p>只接受 .bin 檔案；上傳後會自動簽署與發佈。</p>
        </div>
        <form ref={formRef} onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="field-label">韌體檔案 (.bin)</label>
            <div className="file-input-wrapper">
              <input
                id="firmware-file"
                type="file"
                name="firmware"
                className="simple-file-input"
                accept=".bin"
                required
                onChange={event => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFileName(file ? file.name : '');
                }}
              />
              <label htmlFor="firmware-file">
                <div className="file-dropzone">
                  <span className="file-dropzone-button">
                    <span className="file-dropzone-plus">+</span>
                    選擇 .bin 檔案
                  </span>
                  <span className="file-dropzone-hint">或拖曳檔案到這裡</span>
                </div>
              </label>
            </div>
            <span className="file-dropzone-meta">單一檔案上限 8 MB</span>
          </div>

          <div className="form-group">
            <label>
              裝置型號
              <select name="model" defaultValue="ESP32-S3-DevKit" required className="form-select">
                <option value="ESP32-S3-DevKit">ESP32-S3-DevKit</option>
                <option value="ESP32-S3-Mini">ESP32-S3-Mini</option>
                <option value="ESP8266-12F">ESP8266-12F</option>
              </select>
            </label>
          </div>

          <div className="form-group">
            <label>
              版本號
              <input type="text" name="version" placeholder="2.4.2" required />
            </label>
            <span className="version-meta">格式：主版號.次版號.修訂號</span>
          </div>

          <div className="form-group">
            <label>
              更新說明
              <textarea
                name="description"
                className="text-area-input"
                rows={4}
                placeholder="這一版改了什麼？"
              />
            </label>
          </div>

          {message && <p className="help-text">{message}</p>}

          <button type="submit" className="submit-btn" disabled={submitting}>
            上傳並發佈
          </button>
        </form>
      </div>
    </div>
  );
}
