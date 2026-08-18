import FirmwareList from "../views/FirmwareList"
import FirmwareUpload from "../views/FirmwareUpload"
import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/context';
import "./Firmware.css"

interface Firmware {
    id: number;
    model: string;
    version: string;
    filename: string;
    signature: string;
    sha256: string;
    created_at: string;
    size?: number; // Size in bytes
    devices_using?: number;
}

export default function Firmware() {
    const { session } = useAuth();
    const [firmwares, setfirmwares] = useState<Firmware[]>([]);

    const groupedFirmwares = useMemo(() => {
        const groups = new Map<string, Firmware[]>();

        for (const firmware of firmwares) {
            const items = groups.get(firmware.model) ?? [];
            items.push(firmware);
            groups.set(firmware.model, items);
        }

        return [...groups.entries()]
            .map(([model, items]) => {
                const sorted = [...items].sort(
                    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
                );

                return {
                    model,
                    items: sorted,
                    latest: sorted[0],
                    count: sorted.length,
                    totalDevices: sorted.reduce((sum, item) => sum + (item.devices_using ?? 0), 0),
                };
            })
            .sort((left, right) => new Date(right.latest.created_at).getTime() - new Date(left.latest.created_at).getTime());
    }, [firmwares]);

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

    return (
        <div className="firmware-page">
            <div className="main-card-header firmware-dashboard-header">
                <div className="header-titles">
                    <h1 className="text-xl font-bold text-primary">韌體管理</h1>
                    <p className="text-xs text-secondary">上傳新版韌體並追蹤每個型號的版本歷史，裝置會在下次開機時自動更新。</p>
                </div>

                <div className="firmware-summary">
                    <span className="firmware-summary-item font-mono text-xs text-primary">{groupedFirmwares.length} 個型號</span>
                    <span className="firmware-summary-item font-mono text-xs text-primary">{firmwares.length} 個版本</span>
                    <span className="firmware-summary-item font-mono text-xs text-primary">0 台裝置</span>
                </div>
            </div>
            <div className="firmware-manage-card">
                <FirmwareUpload />
                <FirmwareList groupedFirmwares={groupedFirmwares} />
            </div>
        </div>
    );
}