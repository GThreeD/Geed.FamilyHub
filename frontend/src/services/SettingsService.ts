import { HttpService } from './HttpService';

export type AutomationSettings = Record<string, unknown>;
export class SettingsService {
  static get() {
    return HttpService.request<AutomationSettings>('/api/settings');
  }
  static update(settings: AutomationSettings) {
    return HttpService.request<unknown>('/api/settings', 'PUT', settings);
  }
}
