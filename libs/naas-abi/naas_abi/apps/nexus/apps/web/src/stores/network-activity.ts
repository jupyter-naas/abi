'use client';

import { create } from 'zustand';

interface NetworkActivityState {
  inflight: number;
  totalStarted: number;
  totalCompleted: number;
  sessionStartedAt: number;
  begin: () => void;
  end: () => void;
}

export const useNetworkActivityStore = create<NetworkActivityState>((set) => ({
  inflight: 0,
  totalStarted: 0,
  totalCompleted: 0,
  sessionStartedAt: Date.now(),
  begin: () =>
    set((state) => ({
      inflight: state.inflight + 1,
      totalStarted: state.totalStarted + 1,
    })),
  end: () =>
    set((state) => ({
      inflight: Math.max(0, state.inflight - 1),
      totalCompleted: state.totalCompleted + 1,
    })),
}));

export function trackNetworkActivity<T>(promise: Promise<T>): Promise<T> {
  const { begin, end } = useNetworkActivityStore.getState();
  begin();
  return promise.finally(end);
}
