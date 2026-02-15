/** REST API client for physio-sync backend. */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// Devices
export const getDevices = () => request<import("./types").Device[]>("/api/devices/");
export const getDevice = (id: number) => request<import("./types").Device>(`/api/devices/${id}`);
export const createDevice = (body: {
  name: string;
  type: string;
  address?: string;
  sample_rate?: number;
  channels?: Record<string, unknown>[];
  config?: Record<string, unknown>;
}) =>
  request<import("./types").Device>("/api/devices/", { method: "POST", body: JSON.stringify(body) });

// Recordings
export const getRecordings = () => request<import("./types").Recording[]>("/api/recordings/");
export const getRecording = (id: number) => request<import("./types").Recording>(`/api/recordings/${id}`);
export const createRecording = (body: {
  name: string;
  description?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}) =>
  request<import("./types").Recording>("/api/recordings/", { method: "POST", body: JSON.stringify(body) });
export const startRecording = (id: number) =>
  request<import("./types").Recording>(`/api/recordings/${id}/start`, { method: "POST" });
export const stopRecording = (id: number) =>
  request<import("./types").Recording>(`/api/recordings/${id}/stop`, { method: "POST" });
