import FirmwareList from "../views/FirmwareList"
import FirmwareUpload from "../views/FirmwareUpload"
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/context';
import { compareVersions, pickLatestActive } from '../version';
import "./Firmware.css"

/* Every field the `/api/firmware/list` response model declares. Anything not
  on that list does not exist: there is no device-usage count on a firmware row,
  and a UI that shows one shows a constant. */
export interface Firmware {
    id: number;
    model: string;
    version: string;
    filename: string;
    original_filename: string | null;
    signature: string;
    sha256: string;
    size_bytes: number;
    notes: string | null;
    active: boolean;
    created_at: string;
}

export interface FirmwareGroup {
    model: string;
    items: Firmware[];
    latest: Firmware | undefined;
    count: number;
    activeCount: number;
}

export default function Firmware() {
    const { session } = useAuth();
    const [firmwares, setFirmwares] = useState<Firmware[]>([]);

    const groupedFirmwares = useMemo<FirmwareGroup[]>(() => {
        const groups = new Map<string, Firmware[]>();

        for (const firmware of firmwares) {
            const items = groups.get(firmware.model) ?? [];
            items.push(firmware);
            groups.set(firmware.model, items);
        }

        return [...groups.entries()]
            .map(([model, items]) => {
                // Newest first by version, not by upload time. A hotfix on an
                // older line lands last and is not the newest thing there is.
                const sorted = [...items].sort(
                    (left, right) => compareVersions(right.version, left.version) || right.id - left.id,
                );

                return {
                    model,
                    items: sorted,
                    latest: pickLatestActive(items),
                    count: sorted.length,
                    activeCount: items.filter(item => item.active).length,
                };
            })
            .sort((left, right) => left.model.localeCompare(right.model));
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
            .then(setFirmwares)
            .catch(e => console.error("Failed to fetch firmwares:", e));
    }, [session]);

    // The withdraw route answers with the updated row, so swap it in rather than
    // refetching the list and racing the effect above.
    const handleWithdrawn = useCallback((updated: Firmware) => {
        setFirmwares(prev => prev.map(fw => (fw.id === updated.id ? updated : fw)));
    }, []);

    const withdrawnCount = firmwares.filter(fw => !fw.active).length;

    return (
        <div className="firmware-page">
            <div className="main-card-header firmware-dashboard-header">
                <div className="header-titles">
                    <h1 className="text-xl font-bold text-primary">Firmware</h1>
                    <p className="text-xs text-secondary">Publish a new version and track the release history of each model. Devices pick it up on their next check.</p>
                </div>

                <div className="firmware-summary">
                    <span className="firmware-summary-item font-mono text-xs text-primary">{groupedFirmwares.length} models</span>
                    <span className="firmware-summary-item font-mono text-xs text-primary">{firmwares.length} versions</span>
                    {withdrawnCount > 0 && (
                        <span className="firmware-summary-item font-mono text-xs text-primary">{withdrawnCount} withdrawn</span>
                    )}
                </div>
            </div>
            <div className="firmware-manage-card">
                <FirmwareUpload />
                <FirmwareList groupedFirmwares={groupedFirmwares} onWithdrawn={handleWithdrawn} />
            </div>
        </div>
    );
}
