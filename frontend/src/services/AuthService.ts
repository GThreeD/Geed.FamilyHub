import { HttpService } from './HttpService';
import type { User } from '../api';

export type CredentialType = 'pin' | 'pattern';
export interface LoginResult {
  user: User;
  csrf_token: string;
}
export interface InitialAdmin {
  username: string;
  display_name: string;
  credential_type: CredentialType;
  credential: string;
}

export class AuthService {
  static setupStatus() {
    return HttpService.request<{ needs_setup: boolean }>('/api/auth/setup-status');
  }
  static setupAdmin(data: InitialAdmin) {
    return HttpService.request<unknown>('/api/auth/setup', 'POST', data);
  }
  static async login(username: string, credential: string) {
    const session = await HttpService.request<LoginResult>('/api/auth/login', 'POST', {
      username,
      credential,
    });
    HttpService.setCsrfToken(session.csrf_token);
    return session;
  }
  static async currentUser() {
    const session = await HttpService.request<LoginResult>('/api/auth/me');
    HttpService.setCsrfToken(session.csrf_token);
    return session;
  }
  static async logout() {
    try {
      await HttpService.request<unknown>('/api/auth/logout', 'POST', {});
    } finally {
      HttpService.setCsrfToken('');
    }
  }
}
