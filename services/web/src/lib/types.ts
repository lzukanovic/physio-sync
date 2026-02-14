/** Shared TypeScript types for physio-sync frontend. */

export interface Device {
  id: number;
  name: string;
  type: "bitalino" | "tobii" | "scanner";
  address: string | null;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Recording {
  id: number;
  name: string;
  status: "created" | "running" | "stopped" | "exported";
  started_at: string | null;
  stopped_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SensorSample {
  timestamp_us: number;
  device_id: number;
  channel: string;
  value: number;
  sequence?: number;
}
