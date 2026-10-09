/** Shared HTTP transport. CSRF and session cookies are managed here only. */
let csrfToken = '';

export class HttpService {
  static setCsrfToken(token: string): void {
    csrfToken = token;
  }

  static async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken;

    const response = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload: unknown = await response.json().catch(() => {
      throw new Error('Ungültige Serverantwort');
    });
    if (!response.ok) {
      const message =
        typeof payload === 'object' && payload !== null && 'error' in payload
          ? String(payload.error)
          : `HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload as T;
  }
}
