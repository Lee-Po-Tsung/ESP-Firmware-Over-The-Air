import FirmwareList from "../views/FirmwareList"
import FirmwareUpload from "../views/FirmwareUpload"
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/context';
import { compareVersions, pickLatestActive } from '../version';
import type { Device, Firmware, FirmwareGroup } from '../firmware';
import { usageKey } from '../firmware';
import "./Firmware.css"

export default function Firmware() {
    const { session } = useAuth();
    const [firmwares, setFirmwares] = useState<Firmware[]>([]);
    const [devices, setDevices] = useState<Device[] | null>(null);

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
                };
            })
            .sort((left, right) => left.model.localeCompare(right.model));
    }, [firmwares]);

    /* Which versions are being run right now, counted off what devices report
      rather than off the firmware row. A device on a withdrawn version still
      counts as using it, so this matches on the exact string it sent. */
    const usage = useMemo(() => {
        const counts: Record<string, number> = {};
        for (const device of devices ?? []) {
            if (!device.current_version) continue;
            const key = usageKey(device.model, device.current_version);
            counts[key] = (counts[key] ?? 0) + 1;
        }
        return counts;
    }, [devices]);

    const load = useCallback(() => {
        if (!session) return;
        const auth = { Authorization: `Bearer ${session.token}` };

        fetch('/backend/api/firmware/list', { headers: auth })
            .then(res => {
                if (!res.ok) throw new Error(`Failed to fetch firmwares (HTTP ${res.status})`);
                return res.json() as Promise<Firmware[]>;
            })
            .then(setFirmwares)
            .catch(e => console.error("Failed to fetch firmwares:", e));

        // Left null on failure, which locks withdrawing rather than unlocking
        // it: an empty count would read as "nothing is running this".
        fetch('/backend/api/devices', { headers: auth })
            .then(res => {
                if (!res.ok) throw new Error(`Failed to fetch devices (HTTP ${res.status})`);
                return res.json() as Promise<Device[]>;
            })
            .then(setDevices)
            .catch(e => {
                console.error("Failed to fetch devices:", e);
                setDevices(null);
            });
    }, [session]);

    useEffect(load, [load]);

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
                <FirmwareUpload onUploaded={load} />
                <FirmwareList
                    groupedFirmwares={groupedFirmwares}
                    usage={usage}
                    usageKnown={devices !== null}
                    onWithdrawn={handleWithdrawn}
                />
            </div>
        </div>
    );
}
