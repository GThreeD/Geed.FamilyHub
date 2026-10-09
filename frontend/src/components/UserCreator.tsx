import { useState } from 'react';
import type { Role } from '../api';
import type { CreateUserRequest } from '../services/UserService';
import Pattern from './Pattern';

export default function UserCreator({ create }: { create: (value: CreateUserRequest) => void }) {
  const [name, N] = useState(''),
    [display, D] = useState(''),
    [role, R] = useState<Role>('viewer'),
    [kind, K] = useState<'pin' | 'pattern'>('pin'),
    [credential, C] = useState('');
  return (
    <div className="new-user">
      <h3>Benutzer hinzufügen</h3>
      <div className="fields">
        <label>
          Benutzername
          <input value={name} onChange={(e) => N(e.target.value)} />
        </label>
        <label>
          Anzeigename
          <input value={display} onChange={(e) => D(e.target.value)} />
        </label>
        <label>
          Rolle
          <select value={role} onChange={(e) => R(e.target.value as Role)}>
            <option value="viewer">Betrachter</option>
            <option value="manager">Manager</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <label>
          Anmeldung
          <select
            value={kind}
            onChange={(e) => {
              K(e.target.value as 'pin' | 'pattern');
              C('');
            }}
          >
            <option value="pin">PIN</option>
            <option value="pattern">Muster</option>
          </select>
        </label>
      </div>
      {kind === 'pin' ? (
        <label>
          PIN
          <input
            type="password"
            inputMode="numeric"
            value={credential}
            onChange={(e) => C(e.target.value)}
            placeholder="6–12 Ziffern"
          />
        </label>
      ) : (
        <Pattern value={credential} onChange={C} />
      )}
      <button
        className="primary"
        onClick={() => {
          create({
            username: name,
            display_name: display,
            role,
            credential_type: kind,
            credential,
          });
          C('');
        }}
      >
        Benutzer erstellen
      </button>
    </div>
  );
}
