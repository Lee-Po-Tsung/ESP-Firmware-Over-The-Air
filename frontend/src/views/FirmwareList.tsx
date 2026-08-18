import { useState } from 'react';
import './FirmwareList.css';

interface Firmware {
  id: number;
  model: string;
  version: string;
  filename: string;
  signature: string;
  sha256: string;
  created_at: string;
  size?: number;
  devices_using?: number;
}

export default function FirmwareList({ groupedFirmwares }: {
  groupedFirmwares: {
    model: string;
    items: Firmware[];
    latest: Firmware;
    count: number;
    totalDevices: number;
  }[]
}) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [hasInitialized, setHasInitialized] = useState(false);

  // Initialize expanded state once when groupedFirmwares is available
  if (!hasInitialized && groupedFirmwares.length > 0) {
    setExpandedGroups(new Set(groupedFirmwares.map(g => g.model)));
    setHasInitialized(true);
  }
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const toggleGroup = (model: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(model)) {
      newExpanded.delete(model);
    } else {
      newExpanded.add(model);
    }
    setExpandedGroups(newExpanded);
  };

  const handleDeleteClick = (id: number) => {
    setDeletingId(id);
  };

  const handleDeleteConfirm = async (id: number, model: string, version: string) => {
    setDeleting(true);
    try {
      // TODO: Call actual delete API
      console.log(`Deleting ${model} v${version} (id: ${id})`);
      // await fetch(`/backend/api/firmware/${id}`, { method: 'DELETE' });
    } finally {
      setDeleting(false);
      setDeletingId(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeletingId(null);
  };

  function formatTimestamp(value: string) {
    const d = new Date(value);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
  }

  function formatSize(bytes?: number) {
    if (!bytes) return '';
    if (bytes >= 1048576) {
      return (bytes / 1048576).toFixed(2) + ' MB';
    } else {
      return Math.round(bytes / 1024) + ' KB';
    }
  }

  return (
    <div className="page-wrapper">
      <div className="main-card">
        <div className="main-card-body">
          <div className="firmware-stack">
            {groupedFirmwares.length === 0 ? (
              <div className="fw-empty-state text-sm text-secondary">目前沒有韌體版本。</div>
            ) : (
              groupedFirmwares.map((group) => {
                const isExpanded = expandedGroups.has(group.model);

                return (
                  <div key={group.model} className="fw-group-card">
                    <div className="fw-group-header">
                      <div className="fw-group-left">
                        <div className="fw-group-title-row">
                          <span className="fw-group-model font-mono text-lg text-primary">{group.model}</span>
                          <span className="badge badge-success">最新 v{group.latest.version}</span>
                        </div>
                        <div className="fw-group-subtitle font-mono text-xs text-secondary">
                          {group.totalDevices} 台裝置 ‧ 上次發佈 {formatTimestamp(group.latest.created_at)}
                        </div>
                      </div>
                      <div className="fw-group-right">
                        <span className="fw-group-toggle-text font-mono text-base text-primary" onClick={() => toggleGroup(group.model)}>
                          {isExpanded ? '收合歷史' : '展開歷史'} ({group.count})
                        </span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="fw-history-list">
                        {group.items.map((item) => {
                          const isLatest = item.id === group.latest.id;
                          const deviceCount = item.devices_using ?? 0;
                          const isDeleting = deletingId === item.id;

                          return (
                            <div key={item.id} className="fw-history-row">
                              <div className="fw-history-version font-mono text-sm text-primary">v{item.version}</div>
                              <div className="fw-history-file">
                                <div className="fw-file-name font-mono text-xs text-primary">{item.filename}</div>
                                <div className="fw-file-meta font-mono text-xs text-tertiary">
                                  {item.size ? formatSize(item.size) + ' ‧ ' : ''}{formatTimestamp(item.created_at)}
                                </div>
                              </div>
                              <div className="fw-history-right">
                                {isLatest ? (
                                  <div className="fw-history-status font-mono text-xs text-tertiary">目前最新版，無法刪除</div>
                                ) : deviceCount > 0 ? (
                                  <div className="fw-history-status font-mono text-xs text-tertiary">{deviceCount} 台裝置在用，無法刪除</div>
                                ) : isDeleting ? (
                                  <div className="fw-delete-confirm">
                                    <span className="fw-delete-warning font-mono text-xs text-tertiary">刪除後無法復原</span>
                                    <button
                                      className="btn btn-error btn-outline"
                                      onClick={() => handleDeleteConfirm(item.id, group.model, item.version)}
                                      disabled={deleting}
                                    >
                                      確定刪除
                                    </button>
                                    <button
                                      className="btn btn-secondary"
                                      onClick={handleDeleteCancel}
                                      disabled={deleting}
                                    >
                                      取消
                                    </button>
                                  </div>
                                ) : (
                                  <button
                                    className="btn btn-outline"
                                    onClick={() => handleDeleteClick(item.id)}
                                  >
                                    刪除
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
