import { HttpService } from './HttpService';
import type { TV } from '../api';

export type UsageStats = {
  days: { day: string; seconds: number }[];
  sessions: { id: number; started_at: string; ended_at: string | null; duration_seconds: number }[];
  session_count: number;
};

export type TvLock = {
  mode: 'until_tomorrow' | 'indefinite';
  expires_at: string | null;
  created_at: string;
};

export class DeviceService {
  static powerOff(id: string) {
    return HttpService.request<{ ok: boolean; sent: boolean }>(
      `/api/tvs/${encodeURIComponent(id)}/power`,
      'POST',
      {},
    );
  }
  static create(tv: TV) {
    return HttpService.request<TV>('/api/tvs', 'POST', tv);
  }
  static remove(id: string) {
    return HttpService.request(`/api/tvs/${encodeURIComponent(id)}`, 'DELETE');
  }
  static statistics(id: string) {
    return HttpService.request<UsageStats>(`/api/tvs/${encodeURIComponent(id)}/statistics`);
  }
  static lock(id: string) {
    return HttpService.request<{ lock: TvLock | null }>(`/api/tvs/${encodeURIComponent(id)}/lock`);
  }
  static setLock(id: string, mode: TvLock['mode']) {
    return HttpService.request<{ lock: TvLock }>(
      `/api/tvs/${encodeURIComponent(id)}/lock`,
      'POST',
      { mode },
    );
  }
  static unlock(id: string) {
    return HttpService.request(`/api/tvs/${encodeURIComponent(id)}/lock`, 'DELETE');
  }
}
