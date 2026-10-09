import { HttpService } from './HttpService';
import type { TV, TVStatus } from '../api';

export class TvService {
  static list() {
    return HttpService.request<TV[]>('/api/tvs');
  }
  static status(tvId: string) {
    return HttpService.request<TVStatus>(`/api/tvs/${encodeURIComponent(tvId)}/status`);
  }
  static update(tv: TV) {
    return HttpService.request<unknown>(`/api/tvs/${encodeURIComponent(tv.tv_id)}`, 'PUT', tv);
  }
}
