import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '../auth/context';
import './FirmwareList.css';

interface Firmware {
  id: number;
  model: string;
  version: string;
  filename: string;
  original_filename: string | null;
  signature: string;
  sha256: string;
  active: boolean;
  created_at: string;
}

export default function FirmwareList() {
  const { session } = useAuth();
  const [firmwares, setfirmwares] = useState<Firmware[]>([]);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [withdrawingId, setWithdrawingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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

  // Nothing is locked. Withdrawing the newest version is the whole point of the
  // feature, and withdrawing one that devices are running harms nothing: no file
  // is removed, so a download already in flight finishes and those devices keep
  // running what they have.
  //
  // The one case worth warning about is a model losing its last active version.
  // `get_latest_for_model` then finds nothing, `POST /api/check` answers 403 to
  // every device of that model, and no amount of waiting fixes it. Recoverable
  // by publishing again, so this warns rather than blocks.
  function isLastActiveForModel(target: Firmware): boolean {
    return firmwares.filter(fw => fw.model === target.model && fw.active).length === 1;
  }

  function openConfirm(id: number) {
    setConfirmingId(id);
    setMessage(null);
  }

  function cancelConfirm() {
    setConfirmingId(null);
    setMessage(null);
  }

  async function withdraw(id: number) {
    setWithdrawingId(id);
    setMessage(null);

    try {
      const res = await fetch(`/backend/api/firmware/${id}/deactivate`, {
        method: 'POST',
        headers: session ? { Authorization: `Bearer ${session.token}` } : undefined,
      });

      if (res.status === 401) {
        setMessage('Session expired. Please log in again.');
        return;
      }
      if (res.status === 403) {
        setMessage('Only admin accounts can withdraw a version.');
        return;
      }
      if (res.status === 404) {
        setMessage('That version is no longer on record.');
        return;
      }
      if (!res.ok) {
        setMessage(`Withdraw failed (HTTP ${res.status})`);
        return;
      }

      // The route answers with the updated row, so swap it in rather than
      // refetching the list and racing the effect above.
      const updated = await res.json() as Firmware;
      setfirmwares(prev => prev.map(fw => (fw.id === updated.id ? updated : fw)));
      setConfirmingId(null);
    } catch {
      setMessage('Cannot reach backend. Please make sure API server is running on port 1234.');
    } finally {
      setWithdrawingId(null);
    }
  }

  // Absent rather than disabled: upload and withdraw are both admin-gated, and
  // an operator has no path to either.
  const canWithdraw = session?.role === 'admin';

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
              <div
                key={fw.id}
                className={fw.active ? 'fw-row-card' : 'fw-row-card fw-row-card-withdrawn'}
              >
                <div className="fw-row-header">
                  <div className="fw-identity">
                    <h3 className="fw-model">{fw.model}</h3>
                    <span className="fw-badge">{fw.version}</span>
                    {/* Withdrawn versions stay in the list. Hiding them would make
                        one indistinguishable from a version that never existed. */}
                    {!fw.active && <span className="fw-badge fw-badge-withdrawn">Withdrawn</span>}
                  </div>

                  <div className="fw-row-meta">
                    <div className="fw-date">
                      Uploaded: {new Date(fw.created_at).toLocaleString()}
                    </div>

                    {canWithdraw && fw.active && confirmingId !== fw.id && (
                      <button
                        type="button"
                        className="fw-withdraw-btn"
                        onClick={() => openConfirm(fw.id)}
                      >
                        Withdraw
                      </button>
                    )}
                  </div>
                </div>

                {canWithdraw && fw.active && confirmingId === fw.id && (
                  <div className="fw-confirm">
                    <p className="fw-confirm-text">
                      Stop offering {fw.version} to {fw.model} devices? The file stays on
                      the server and devices already running it are untouched.
                    </p>

                    {isLastActiveForModel(fw) && (
                      <p className="fw-confirm-warning">
                        This is the last active version for {fw.model}. Every device of this
                        model will get an error on its next check until you publish another
                        version.
                      </p>
                    )}

                    {message && <p className="fw-confirm-error">{message}</p>}

                    <div className="fw-confirm-actions">
                      <button
                        type="button"
                        className="fw-confirm-btn"
                        onClick={() => withdraw(fw.id)}
                        disabled={withdrawingId === fw.id}
                      >
                        {withdrawingId === fw.id ? 'Withdrawing...' : 'Confirm withdraw'}
                      </button>
                      <button
                        type="button"
                        className="fw-cancel-btn"
                        onClick={cancelConfirm}
                        disabled={withdrawingId === fw.id}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                <div className="fw-details-grid">
                  <div className="fw-detail-item">
                    <span className="fw-detail-label">File</span>
                    {/* filename is the sha256 blob key, shown one row down */}
                    <div className="fw-detail-value">{fw.original_filename ?? fw.filename}</div>
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
