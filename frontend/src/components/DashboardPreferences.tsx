import { useEffect, useState } from 'react';
import {
  PreferencesService,
  type DashboardPreferences as Preferences,
} from '../services/PreferencesService';

type Props = {
  preferences: Preferences;
  onSaved: (preferences: Preferences) => void;
  act: (action: () => Promise<unknown>) => Promise<void>;
};
const TILES = [
  ['show_tv_count', 'Fernseher'],
  ['show_online_count', 'Online erkannt'],
  ['show_blocked_count', 'Aktive Sperren'],
] as const;

export default function DashboardPreferences({ preferences, onSaved, act }: Props) {
  const [draft, setDraft] = useState(preferences);
  const [loading, setLoading] = useState(false);
  useEffect(() => setDraft(preferences), [preferences]);
  async function save() {
    setLoading(true);
    try {
      await act(async () => onSaved(await PreferencesService.update(draft)));
    } finally {
      setLoading(false);
    }
  }
  return (
    <section className="panel narrow">
      <h2>Deine Übersicht</h2>
      <p className="muted">
        Diese Kacheln werden nur für dein Benutzerkonto ein- oder ausgeblendet.
      </p>
      {TILES.map(([key, label]) => (
        <label className="lock-switch-row" key={key}>
          <span className="lock-switch-title">{label}</span>
          <span className="lock-switch-control">
            <input
              type="checkbox"
              role="switch"
              checked={draft[key]}
              disabled={loading}
              onChange={(event) => setDraft({ ...draft, [key]: event.target.checked })}
            />
            <span className="lock-switch-track" aria-hidden="true" />
          </span>
          <span className="lock-switch-state">{draft[key] ? 'Sichtbar' : 'Ausgeblendet'}</span>
        </label>
      ))}
      <button className="primary" disabled={loading} onClick={() => void save()}>
        Übersicht speichern
      </button>
    </section>
  );
}
