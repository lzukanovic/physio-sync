/** Shared TypeScript types for physio-sync frontend. */

export interface Device {
  id: number;
  name: string;
  type: "bitalino" | "tobii" | "scanner";
  address: string | null;
  sample_rate: number | null;
  channels: Record<string, unknown>[];
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Recording {
  id: number;
  name: string;
  description: string | null;
  tags: string[];
  status: "created" | "running" | "stopped" | "exported";
  started_at: string | null;
  stopped_at: string | null;
  device_configs: Record<string, unknown>[];
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
