import React, { useRef, useState } from 'react';
import { useAuth } from '../auth/context';
import './FirmwareUpload.css';

// Outcome rides alongside the text instead of being sniffed back out of it.
// The alert styling used to key off the string containing "success", which any
// rewording (a translation included) silently turns into a permanent error style.
type Notice = { text: string; ok: boolean };

export default function FirmwareUpload({ onPublished }: { onPublished: () => void }) {
  const { session } = useAuth();
  const formRef = useRef<HTMLFormElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>('');

  async function handleSubmit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    const form = formRef.current;
    if (!form || !form.reportValidity()) {
      return;
    }

    setSubmitting(true);
    setNotice(null);

    try {
      const res = await fetch('/backend/firmware/upload', {
        method: 'POST',
        headers: session ? { Authorization: `Bearer ${session.token}` } : undefined,
        body: new FormData(form),
      });

      if (res.status === 401) {
        setNotice({ text: '登入階段已過期，請重新登入。', ok: false });
        return;
      }
      if (res.status === 403) {
        setNotice({ text: '只有管理員帳號可以發布韌體。', ok: false });
        return;
      }
      // Several distinct causes share these codes, and the backend already
      // names which one in `detail`, so show it rather than mirroring the list.
      if (res.status === 400 || res.status === 409) {
        const body = await res.json().catch(() => null);
        setNotice({ text: body?.detail ?? `上傳失敗（HTTP ${res.status}）`, ok: false });
        return;
      }
      if (!res.ok) {
        setNotice({ text: `上傳失敗（HTTP ${res.status}）`, ok: false });
        return;
      }

      setNotice({ text: '韌體已發布。', ok: true });
      form.reset();
      setSelectedFileName('');
      // The list is fetched once when the session appears, so without this the
      // version just published is missing from it until the page is reloaded.
      onPublished();
    } catch {
      setNotice({ text: '無法連線到後端，請確認 API 伺服器正在執行。', ok: false });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="upload-container">
      <div className="card upload-card">
        <div className="upload-header">
          <h1 className="text-xl font-bold text-primary">發布韌體</h1>
          <p className="text-xs text-secondary">上傳後由伺服器簽署。同型號的裝置會在下一次回報時取得這個版本。</p>
        </div>
        <form ref={formRef} onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="firmware-file">韌體映像檔（.bin）</label>
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
                  + 選擇 .bin 檔
                </span>
                {selectedFileName
                  ? <span className="form-help font-mono">{selectedFileName}</span>
                  : <span className="form-help">或拖曳檔案到這裡</span>}
              </div>
            </div>
          </div>

          {/* Free text, not a list. `model` is whatever string the device sends
              in `POST /api/check`, so a fixed list here is a second source of
              truth that silently blocks any board not on it. */}
          <div className="form-group">
            <label className="form-label" htmlFor="firmware-model">裝置型號</label>
            <input id="firmware-model" type="text" className="form-input" name="model" placeholder="ESP32" required />
            <span className="form-help">必須與 sketch 裡的 DEVICE_MODEL 完全一致。</span>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="firmware-version">版本</label>
            <input id="firmware-version" type="text" className="form-input" name="version" placeholder="2.4.2" required />
            <span className="form-help">三段數字：主版本.次版本.修訂號</span>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="firmware-notes">版本說明</label>
            <textarea
              id="firmware-notes"
              name="notes"
              className="form-input"
              rows={4}
              placeholder="這個版本改了什麼？"
              style={{ resize: 'vertical' }}
            />
          </div>

          {notice && (
            <div className={`alert ${notice.ok ? 'alert-info' : 'alert-error'}`}>
              {notice.text}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.9rem', padding: '0.82rem' }} disabled={submitting}>
            {submitting ? '上傳中...' : '上傳並發布'}
          </button>
        </form>
      </div>
    </div>
  );
}
