import { HttpService } from './HttpService';

export type BonusGrant = {
  id: number;
  granted_seconds: number;
  consumed_seconds: number;
  expires_at: string;
  created_at: string;
};

export class BonusService {
  static list(tvId: string) {
    return HttpService.request<BonusGrant[]>(`/api/tvs/${encodeURIComponent(tvId)}/bonus`);
  }

  static revoke(tvId: string, id: number) {
    return HttpService.request<{ ok: boolean }>(
      `/api/tvs/${encodeURIComponent(tvId)}/bonus/${id}`,
      'DELETE',
    );
  }

  static grant(tvId: string, minutes: number) {
    return HttpService.request<unknown>(`/api/tvs/${encodeURIComponent(tvId)}/bonus`, 'POST', {
      minutes,
    });
  }
}
