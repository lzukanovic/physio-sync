"use client";

import { useEffect, useRef, useState } from "react";
import { createLiveSocket } from "@/lib/ws";
import type { SensorSample } from "@/lib/types";

export function useRealtimeData(maxSamples = 500) {
  const [samples, setSamples] = useState<SensorSample[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<ReturnType<typeof createLiveSocket> | null>(null);

  useEffect(() => {
    socketRef.current = createLiveSocket(
      (incoming) => {
        setSamples((prev) => {
          const next = [...prev, ...incoming];
          return next.length > maxSamples ? next.slice(-maxSamples) : next;
        });
      },
      setConnected,
    );

    return () => {
      socketRef.current?.close();
    };
  }, [maxSamples]);

  return { samples, connected };
}
