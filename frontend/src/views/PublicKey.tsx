import { useState } from 'react';
import { useAuth } from '../auth/context';
import { generateKeyPair } from '../crypto/signing';
import './PublicKey.css';

// Where an account's signing identity is set. The server holds no private key
// at all: it verifies each upload against the public key stored here, so a
// leaked server cannot produce firmware any device would accept.
export default function PublicKey() {
  const { session, authFetch, setHasPublicKey } = useAuth();
  const [pem, setPem] = useState('');
  const [expanded, setExpanded] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [handedOver, setHandedOver] = useState(false);

  const hasKey = session?.account.hasPublicKey ?? false;

  // Generated here rather than on the server, which is the same reason the
  // server holds no key of its own: the private half exists only on the
  // machine that publishes. It leaves this page once, as a file, and the only
  // copy after that is the operator's.
  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const { publicPem, privatePem } = await generateKeyPair();
      const url = URL.createObjectURL(new Blob([privatePem], { type: 'application/x-pem-file' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'private_key.pem';
      link.click();
      URL.revokeObjectURL(url);
      setPem(publicPem);
      setHandedOver(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : '產生金鑰失敗。');
    } finally {
      setGenerating(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const res = await authFetch('/backend/api/auth/public-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ public_key: pem }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `設定失敗（HTTP ${res.status}）`);
      }
      setHasPublicKey(true);
      setPem('');
      setHandedOver(false);
      setExpanded(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card key-card">
      <div className="key-header">
        <div>
          <h2 className="text-base font-medium text-primary">簽章公鑰</h2>
          <p className="text-xs text-secondary">
            伺服器不保管任何私鑰，上傳的韌體是拿這把公鑰驗章的。私鑰留在你自己的機器上。
          </p>
        </div>
        <span className={hasKey ? 'badge badge-success' : 'badge badge-warning'}>
          {hasKey ? '已設定' : '尚未設定'}
        </span>
      </div>

      {!hasKey && (
        <div className="alert alert-warning">
          <span>
            <span className="alert-title">還不能發布韌體。</span>
            按下面的按鈕產生一組金鑰，私鑰會存成檔案下載到你的電腦，公鑰會填進下面那格。
            同一把公鑰也要放進每台裝置的 config.json，裝置才驗得過下載回來的韌體。
            已經有金鑰的話（例如用 <code className="font-mono">generate_keys.py</code> 產的），
            直接把 <code className="font-mono">public_key.pem</code> 的內容貼進去。
          </span>
        </div>
      )}

      {expanded || !hasKey ? (
        <form className="key-form" onSubmit={handleSubmit}>
          <textarea
            className="form-input font-mono key-input"
            rows={6}
            placeholder="-----BEGIN PUBLIC KEY-----"
            value={pem}
            onChange={e => setPem(e.target.value)}
            required
          />

          {error && (
            <div className="alert alert-error">
              <span className="alert-title">設定失敗：</span>
              {error}
            </div>
          )}

          {handedOver && (
            <div className="alert alert-warning">
              <span className="alert-title">私鑰只會給你這一次。</span>
              它沒有存在伺服器上，這一頁關掉就沒有了。發布韌體要用它簽章，弄丟的話只能重產一把，
              並且重燒每一台裝置的 config.json。
            </div>
          )}

          <div className="key-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? '產生中...' : '在瀏覽器產生一組'}
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? '設定中...' : hasKey ? '換成這把' : '設定公鑰'}
            </button>
            {hasKey && (
              <button type="button" className="btn btn-secondary" onClick={() => setExpanded(false)}>
                取消
              </button>
            )}
          </div>

          {hasKey && (
            <p className="form-help">
              換金鑰只影響之後上傳的版本。已經發布的韌體帶著舊金鑰簽出來的簽章，裝置也還是拿自己
              config.json 裡那把在驗，所以不重燒裝置的話，現場什麼都不會變。
            </p>
          )}
        </form>
      ) : (
        <button
          type="button"
          className="btn btn-secondary key-reopen"
          onClick={() => setExpanded(true)}
        >
          更換公鑰
        </button>
      )}
    </div>
  );
}
