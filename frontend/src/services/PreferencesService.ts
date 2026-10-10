import { HttpService } from './HttpService';

export type DashboardPreferences = {
  show_tv_count: boolean;
  show_online_count: boolean;
  show_blocked_count: boolean;
};
export const DEFAULT_PREFERENCES: DashboardPreferences = {
  show_tv_count: true,
  show_online_count: true,
  show_blocked_count: true,
};
export class PreferencesService {
  static get() {
    return HttpService.request<DashboardPreferences>('/api/auth/preferences');
  }
  static update(preferences: DashboardPreferences) {
    return HttpService.request<DashboardPreferences>('/api/auth/preferences', 'PUT', preferences);
  }
}
