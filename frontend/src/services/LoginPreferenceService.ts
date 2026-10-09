export type LoginMethod = 'pin' | 'pattern';
export interface LoginPreference {
  username: string;
  method: LoginMethod;
}

const KEY = 'stc.login.preference';

export class LoginPreferenceService {
  static load(): LoginPreference | null {
    try {
      const value = JSON.parse(localStorage.getItem(KEY) || 'null');
      return value &&
        typeof value.username === 'string' &&
        (value.method === 'pin' || value.method === 'pattern')
        ? value
        : null;
    } catch {
      return null;
    }
  }

  static save(username: string, method: LoginMethod): void {
    localStorage.setItem(KEY, JSON.stringify({ username, method }));
  }

  static clear(): void {
    localStorage.removeItem(KEY);
  }
}
