"use client";

import { useCallback, useEffect, useState } from "react";
import { getRecordings } from "@/lib/api";
import type { Recording } from "@/lib/types";

export function useRecordings() {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setRecordings(await getRecordings());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load recordings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { recordings, loading, error, refresh };
}
