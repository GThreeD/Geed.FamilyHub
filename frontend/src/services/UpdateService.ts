import { HttpService } from './HttpService';

export type ReleaseInfo = { tag: string; page: string };
export type PreparedUpdate = { tag: string; sha256: string; ready: boolean };

export class UpdateService {
  static latest() {
    return HttpService.request<ReleaseInfo>('/api/updates/latest');
  }

  static prepare() {
    return HttpService.request<PreparedUpdate>('/api/updates/prepare', 'POST');
  }

  static install() {
    return HttpService.request<{ ok: boolean; message: string }>('/api/updates/install', 'POST');
  }
}
