/* The shapes the firmware screens share, and the one helper that keys them.

  Field for field what `/api/firmware/list` and `/api/devices` declare in their
  response models. Anything absent here is absent on the wire: a firmware row
  carries no device count, which is why usage is counted off the devices. */

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

export interface Device {
  device_id: string;
  model: string;
  current_version: string | null;
}

export interface FirmwareGroup {
  model: string;
  items: Firmware[];
  latest: Firmware | undefined;
  count: number;
}

/* A version is identified by its model too: two models can publish 1.0.0 and
  they are different binaries. */
export function usageKey(model: string, version: string) {
  return `${model}|${version}`;
}
