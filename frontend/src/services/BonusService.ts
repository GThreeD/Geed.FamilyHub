import { HttpService } from './HttpService';

export class BonusService {
  static grant(tvId: string, minutes: number, expiresAt: string) {
    return HttpService.request<unknown>(`/api/tvs/${encodeURIComponent(tvId)}/bonus`, 'POST', {
      minutes,
      expires_at: expiresAt,
    });
  }
}
