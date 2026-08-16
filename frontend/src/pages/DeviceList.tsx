import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../auth/context';
import './DeviceList.css';

interface ApiDevice {
  id: number;
  device_id: string;
  model: string;
  current_version: string | null;
  last_seen: string | null;
}

interface Firmware {
  model: string;
  version: string;
  created_at: string;
}

function timeAgo(iso: string | null): string {
  if (!iso) return '從未回報';
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)} 秒前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分鐘前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小時前`;
  return `${Math.floor(hours / 24)} 天前`;
}

function getStatus(iso: string | null): 'online' | 'offline' {
  if (!iso) return 'offline';
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  return seconds <= 60 ? 'online' : 'offline';
}



export default function DeviceList() {
  const { session } = useAuth();
  const [apiDevices, setApiDevices] = useState<ApiDevice[]>([]);
  const [firmwares, setFirmwares] = useState<Firmware[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [time, setTime] = useState(new Date().toLocaleTimeString('zh-TW', { hour12: false }));

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState('全部型號');
  const [selectedStatus, setSelectedStatus] = useState('全部');

  useEffect(() => {
    if (!session) return;
    const fetchData = () => {
      Promise.all([
        fetch('/backend/api/devices', { headers: { Authorization: `Bearer ${session.token}` } }).then(r => {
          if (!r.ok) throw new Error('Failed to fetch devices');
          return r.json();
        }),
        fetch('/backend/api/firmware/list', { headers: { Authorization: `Bearer ${session.token}` } }).then(r => {
          if (!r.ok) throw new Error('Failed to fetch firmwares');
          return r.json();
        })
      ])
        .then(([devs, fws]) => {
          setApiDevices(devs);
          setFirmwares(fws);
          setError(null);
        })
        .catch(e => setError(e instanceof Error ? e.message : String(e)));
    };

    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [session]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString('zh-TW', { hour12: false }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const latestFirmwares = useMemo(() => {
    return firmwares.reduce((acc, fw) => {
      if (!acc[fw.model] || new Date(fw.created_at) > new Date(acc[fw.model].created_at)) {
        acc[fw.model] = fw;
      }
      return acc;
    }, {} as Record<string, Firmware>);
  }, [firmwares]);

  const devices = apiDevices.map(d => {
    const latestFw = latestFirmwares[d.model];
    const is_latest = (latestFw && d.current_version) ? (d.current_version === latestFw.version) : true;

    return {
      id: d.device_id,
      model: d.model,
      current_version: d.current_version || '未知',
      is_latest,
      last_seen: timeAgo(d.last_seen),
      status: getStatus(d.last_seen) as 'online' | 'offline' | 'updating'
    };
  });

  const onlineCount = devices.filter(d => d.status === 'online').length;
  const offlineCount = devices.filter(d => d.status === 'offline').length;
  const updatingCount = devices.filter(d => d.status === 'updating').length;
  const outdatedDevices = devices.filter(d => !d.is_latest);
  const uniqueModels = Array.from(new Set([
    'ESP32-S3-DevKit',
    'ESP32-S3-Mini',
    'ESP8266-12F',
    ...devices.map(d => d.model)
  ]));

  const filteredDevices = devices.filter(d => {
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch = !searchQuery ||
      d.id.toLowerCase().includes(searchLower) ||
      d.model.toLowerCase().includes(searchLower);

    const matchesModel = selectedModel === '全部型號' || d.model === selectedModel;

    let matchesStatus = true;
    if (selectedStatus === '在線') matchesStatus = d.status === 'online';
    if (selectedStatus === '離線') matchesStatus = d.status === 'offline';

    return matchesSearch && matchesModel && matchesStatus;
  });

  return (
    <div className="dev-page">
      <div className="dev-header-area">
        <div className="dev-header-left">
          <h1>裝置監控</h1>
        </div>
        <div className="dev-live-indicator">
          <span className="live-dot"></span>
          即時 · {time}
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span className="alert-title">無法取得資料：</span>
          {error}
        </div>
      )}

      <div className="dev-summary-cards">
        <div className="card dev-card">
          <div className="dev-card-title">在線</div>
          <div className="dev-card-value text-green">{onlineCount}</div>
          <div className="dev-card-desc">心跳正常</div>
        </div>
        <div className="card dev-card">
          <div className="dev-card-title">離線</div>
          <div className="dev-card-value text-red">{offlineCount}</div>
          <div className="dev-card-desc">超過 60 秒未回報</div>
        </div>
        <div className="card dev-card">
          <div className="dev-card-title">更新中</div>
          <div className="dev-card-value text-blue">{updatingCount}</div>
          <div className="dev-card-desc">正在寫入韌體</div>
        </div>
        <div className="card dev-card">
          <div className="dev-card-title">韌體落後</div>
          <div className="dev-card-value text-dark">{outdatedDevices.length}</div>
          <div className="dev-card-desc">回報後會自動更新</div>
        </div>
      </div>

      {outdatedDevices.length > 0 && (
        <div className="alert alert-warning">
          <span className="alert-title">有裝置的韌體版本落後：</span>
          {outdatedDevices.length} 台裝置不是最新韌體：{outdatedDevices.map(d => d.id).join('、')}，這些裝置會在下次回報心跳時自動更新，離線的裝置則要重新上線。
        </div>
      )}

      <div className="data-table-container dev-table-container">
        <div className="data-table-toolbar dev-table-toolbar">
          <div className="search-box">
            <span className="search-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 -960 960 960" width="18px" fill="currentColor">
                <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z" />
              </svg>
            </span>
            <input
              type="text"
              className="form-input"
              placeholder="搜尋名稱或型號"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="dev-table-filters">
            <div className="form-group dev-filter-group">
              <span className="form-label">型號</span>
              <select
                className="form-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                <option value="全部型號">全部型號</option>
                {uniqueModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
            <div className="form-group dev-filter-group">
              <span className="form-label">狀態</span>
              <div className="segmented-control">
                <button
                  className={`segmented-btn ${selectedStatus === '全部' ? 'active' : ''}`}
                  onClick={() => setSelectedStatus('全部')}
                >全部</button>
                <button
                  className={`segmented-btn ${selectedStatus === '在線' ? 'active' : ''}`}
                  onClick={() => setSelectedStatus('在線')}
                >在線</button>
                <button
                  className={`segmented-btn ${selectedStatus === '離線' ? 'active' : ''}`}
                  onClick={() => setSelectedStatus('離線')}
                >離線</button>
              </div>
            </div>
          </div>
        </div>

        <div className="dev-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>裝置</th>
                <th>韌體</th>
                <th>最後回報</th>
                <th>狀態</th>
              </tr>
            </thead>
            <tbody>
              {filteredDevices.map(d => (
                <tr key={d.id}>
                  <td className="dev-col-device">
                    <div className="dev-device-info">
                      <span className={`dev-status-dot ${d.status === 'online' ? 'dot-green' : 'dot-red'}`}></span>
                      <div className="dev-device-text">
                        <div className="dev-device-name">{d.id}</div>
                        <div className="dev-device-meta">{d.model}</div>
                      </div>
                    </div>
                  </td>
                  <td className="dev-col-fw">
                    <span className="dev-fw-text">{d.current_version}</span>
                  </td>
                  <td className="dev-col-seen">
                    {d.last_seen}
                  </td>
                  <td className="dev-col-status">
                    {d.status === 'online' ? (
                      <span className="badge badge-success">在線</span>
                    ) : (
                      <span className="badge badge-error">離線</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
