import { useState, type FormEvent } from 'react';
import { Tv } from 'lucide-react';
import type { User } from '../api';
import { AuthService, type CredentialType } from '../services/AuthService';
import { LoginPreferenceService } from '../services/LoginPreferenceService';
import Pattern from './Pattern';

type Props = { setup: boolean; onDone: (user: User) => void };

export default function Access({ setup, onDone }: Props) {
  const preference = LoginPreferenceService.load();
  const [name, setName] = useState(setup ? '' : preference?.username || '');
  const [displayName, setDisplayName] = useState('');
  const [method, setMethod] = useState<CredentialType>(setup ? 'pin' : preference?.method || 'pin');
  const [credential, setCredential] = useState('');
  const [remember, setRemember] = useState(Boolean(preference));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function authenticate(secret: string) {
    if (busy || !name.trim()) return;
    setBusy(true);
    setError('');
    try {
      if (setup) {
        await AuthService.setupAdmin({
          username: name,
          display_name: displayName,
          credential_type: method,
          credential: secret,
        });
      }
      const session = await AuthService.login(name, secret);
      if (remember) LoginPreferenceService.save(name, method);
      else LoginPreferenceService.clear();
      setCredential('');
      onDone(session.user);
    } catch (err) {
      setCredential('');
      setError(err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void authenticate(credential);
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <div className="logo">
          <Tv size={25} />
        </div>
        <h1>{setup ? 'Administrator erstellen' : 'Willkommen zurück'}</h1>
        <label>
          Benutzername
          <input
            required
            autoComplete="username"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        {setup && (
          <label>
            Anzeigename
            <input
              required
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
        )}
        <div className="segmented">
          {(['pin', 'pattern'] as const).map((value) => (
            <button
              type="button"
              key={value}
              className={method === value ? 'active' : ''}
              onClick={() => {
                setMethod(value);
                setCredential('');
              }}
            >
              {value === 'pin' ? 'PIN' : 'Muster'}
            </button>
          ))}
        </div>
        {method === 'pin' ? (
          <label>
            PIN
            <input
              required
              type="password"
              inputMode="numeric"
              minLength={6}
              maxLength={12}
              pattern="[0-9]{6,12}"
              value={credential}
              autoComplete={setup ? 'new-password' : 'current-password'}
              onChange={(event) => setCredential(event.target.value)}
            />
          </label>
        ) : (
          <Pattern
            value={credential}
            disabled={busy}
            onChange={setCredential}
            onComplete={(pattern) => {
              if (!setup) void authenticate(pattern);
            }}
          />
        )}
        <label className="remember-device">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          Benutzer und Anmeldemethode merken
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {(setup || method === 'pin') && (
          <button
            className="primary full"
            disabled={busy || (method === 'pattern' && credential.length < 6)}
          >
            {busy ? 'Bitte warten…' : setup ? 'Erstellen' : 'Anmelden'}
          </button>
        )}
      </form>
    </div>
  );
}
