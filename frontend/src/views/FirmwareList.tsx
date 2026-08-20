import { useState } from 'react';
import { useAuth } from '../auth/context';
import type { Firmware, FirmwareGroup } from '../firmware';
import { usageKey } from '../firmware';
import './FirmwareList.css';

export default function FirmwareList({ groupedFirmwares, usage, usageKnown, onWithdrawn }: {
  groupedFirmwares: FirmwareGroup[];
  usage: Record<string, number>;
  usageKnown: boolean;
  onWithdrawn: (updated: Firmware) => void;
}) {
  const { session } = useAuth();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [hasInitialized, setHasInitialized] = useState(false);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [withdrawingId, setWithdrawingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Initialize expanded state once when groupedFirmwares is available
  if (!hasInitialized && groupedFirmwares.length > 0) {
    setExpandedGroups(new Set(groupedFirmwares.map(g => g.model)));
    setHasInitialized(true);
  }

  // Absent rather than disabled: upload and withdraw are both admin-gated, and
  // an operator has no path to either.
  const canWithdraw = session?.role === 'admin';

  const toggleGroup = (model: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(model)) {
      newExpanded.delete(model);
    } else {
      newExpanded.add(model);
    }
    setExpandedGroups(newExpanded);
  };

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

      onWithdrawn(await res.json() as Firmware);
      setConfirmingId(null);
    } catch {
      setMessage('Cannot reach backend. Please make sure API server is running on port 1234.');
    } finally {
      setWithdrawingId(null);
    }
  }

  function formatTimestamp(value: string) {
    const d = new Date(value);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
  }

  function formatSize(bytes: number) {
    if (bytes >= 1048576) {
      return (bytes / 1048576).toFixed(2) + ' MB';
    }
    return Math.round(bytes / 1024) + ' KB';
  }

  /* Withdrawing is for retiring a version nothing depends on any more. The
    latest one is what every device of the model is told to run, and a version
    devices report running is one a rollback would still be reaching for, so
    both are held. Returns why, or null when the version may go.

    This is the dashboard's rule, not the server's: POST /api/firmware/{id}/
    deactivate applies neither, so anything with a token can still withdraw. */
  function lockReason(group: FirmwareGroup, item: Firmware): string | null {
    if (group.latest?.id === item.id) return 'Latest version, cannot withdraw';
    if (!usageKnown) return 'Device list unavailable, cannot withdraw';

    const running = usage[usageKey(item.model, item.version)] ?? 0;
    if (running > 0) {
      return `${running} device${running === 1 ? '' : 's'} running this, cannot withdraw`;
    }
    return null;
  }

  function lastPublished(group: FirmwareGroup) {
    return group.items.reduce((newest, item) =>
      new Date(item.created_at) > new Date(newest.created_at) ? item : newest,
    ).created_at;
  }

  return (
    <div className="page-wrapper">
      <div className="main-card">
        <div className="main-card-body">
          <div className="firmware-stack">
            {groupedFirmwares.length === 0 ? (
              <div className="fw-empty-state text-sm text-secondary">No firmware versions yet.</div>
            ) : (
              groupedFirmwares.map((group) => {
                const isExpanded = expandedGroups.has(group.model);

                return (
                  <div key={group.model} className="fw-group-card">
                    <div className="fw-group-header">
                      <div className="fw-group-left">
                        <div className="fw-group-title-row">
                          <span className="fw-group-model font-mono text-lg text-primary">{group.model}</span>
                          {group.latest ? (
                            <span className="badge badge-success">Latest v{group.latest.version}</span>
                          ) : (
                            /* Every device of this model gets a 403 on its next check
                              until a version is published again. */
                            <span className="badge badge-warning">No active version</span>
                          )}
                        </div>
                        <div className="fw-group-subtitle font-mono text-xs text-secondary">
                          Last published {formatTimestamp(lastPublished(group))}
                        </div>
                      </div>
                      <div className="fw-group-right">
                        <span className="fw-group-toggle-text font-mono text-base text-primary" onClick={() => toggleGroup(group.model)}>
                          {isExpanded ? 'Collapse history' : 'Expand history'} ({group.count})
                        </span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="fw-history-list">
                        {group.items.map((item) => {
                          const isConfirming = confirmingId === item.id;
                          const locked = lockReason(group, item);

                          return (
                            <div
                              key={item.id}
                              className={item.active ? 'fw-history-row' : 'fw-history-row fw-history-row-withdrawn'}
                            >
                              <div className="fw-history-version font-mono text-sm text-primary">v{item.version}</div>
                              <div className="fw-history-file">
                                <div className="fw-file-name font-mono text-xs text-primary">
                                  {item.original_filename ?? item.filename}
                                </div>
                                <div className="fw-file-meta font-mono text-xs text-tertiary">
                                  {formatSize(item.size_bytes)} ‧ {formatTimestamp(item.created_at)}
                                </div>
                                {item.notes && <div className="fw-file-notes text-xs text-secondary">{item.notes}</div>}
                              </div>
                              <div className="fw-history-right">
                                {/* Withdrawn versions stay in the list. Hiding them would
                                    make one indistinguishable from a version that never
                                    existed. Nothing is offered to bring one back: the
                                    route only deactivates. */}
                                {!item.active ? (
                                  <span className="badge badge-warning">Withdrawn</span>
                                ) : locked ? (
                                  <span className="fw-history-status font-mono text-xs text-tertiary">{locked}</span>
                                ) : !canWithdraw ? null : isConfirming ? (
                                  <div className="fw-withdraw-confirm">
                                    <p className="fw-withdraw-text font-mono text-xs text-tertiary">
                                      Stop offering v{item.version} to {group.model} devices? The file
                                      stays on the server and devices already running it are untouched.
                                    </p>

                                    {message && <p className="fw-withdraw-error text-xs">{message}</p>}

                                    <div className="fw-withdraw-actions">
                                      <button
                                        type="button"
                                        className="btn btn-primary"
                                        onClick={() => withdraw(item.id)}
                                        disabled={withdrawingId === item.id}
                                      >
                                        {withdrawingId === item.id ? 'Withdrawing...' : 'Confirm withdraw'}
                                      </button>
                                      <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={cancelConfirm}
                                        disabled={withdrawingId === item.id}
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <button
                                    type="button"
                                    className="btn btn-outline"
                                    onClick={() => openConfirm(item.id)}
                                  >
                                    Withdraw
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
