/** WebSocket client for real-time sensor data. */

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export function createLiveSocket(
  onMessage: (samples: import("./types").SensorSample[]) => void,
  onStatusChange?: (connected: boolean) => void,
) {
  let ws: WebSocket | null = null;
  let shouldReconnect = true;

  function connect() {
    ws = new WebSocket(`${WS_BASE}/ws/live`);

    ws.onopen = () => {
      onStatusChange?.(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(Array.isArray(data) ? data : [data]);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      onStatusChange?.(false);
      if (shouldReconnect) {
        setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  connect();

  return {
    close() {
      shouldReconnect = false;
      ws?.close();
    },
  };
}
