import { SettingsService } from '../services/SettingsService';

type SettingsViewProps = {
  settings: Record<string, any>;
  setSettings: (value: any) => void;
  act: (action: () => Promise<unknown>) => Promise<void>;
};

const NUMBER_SETTINGS = [
  { key: 'poll_seconds', label: 'Prüfintervall (Sekunden)', min: 2, max: 60, step: 1 },
  { key: 'confirm_online_checks', label: 'Online-Bestätigungen', min: 1, max: 20, step: 1 },
  { key: 'confirm_offline_checks', label: 'Offline-Bestätigungen', min: 2, max: 20, step: 1 },
  {
    key: 'cooldown_seconds',
    label: 'Wartezeit nach Ausschaltversuch (Sekunden)',
    min: 5,
    max: 3600,
    step: 1,
  },
  {
    key: 'power_hold_seconds',
    label: 'Power-Taste halten (Sekunden)',
    min: 0.5,
    max: 5,
    step: 0.5,
  },
] as const;

export default function SettingsView({ settings, setSettings, act }: SettingsViewProps) {
  const numbersValid = NUMBER_SETTINGS.every(({ key, min, max, step }) => {
    const value = settings[key];
    if (value === '' || typeof value !== 'number' || !Number.isFinite(value)) return false;
    return (
      value >= min &&
      value <= max &&
      Math.abs((value - min) / step - Math.round((value - min) / step)) < 1e-8
    );
  });

  function saveSettings() {
    if (!numbersValid) return;
    const { id, ...payload } = settings;
    void act(() => SettingsService.update(payload));
  }

  return (
    <section className="panel narrow">
      <h2>Automatisierung</h2>
      <p className="muted">
        Änderungen wirken ohne Neustart. Der Power-Befehl kann den TV bei falscher Erkennung auch
        einschalten.
      </p>

      <label className="lock-switch-row">
        <span className="lock-switch-title">Sperrmodus</span>
        <span className="lock-switch-control">
          <input
            type="checkbox"
            role="switch"
            aria-label="Sperrmodus"
            checked={!!settings.armed}
            onChange={(event) => setSettings({ ...settings, armed: event.target.checked })}
          />
          <span className="lock-switch-track" aria-hidden="true" />
        </span>
        <span className="lock-switch-state">{settings.armed ? 'Aktiv' : 'Testmodus'}</span>
      </label>

      {NUMBER_SETTINGS.map(({ key, label, min, max, step }) => (
        <label key={key}>
          {label}
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={settings[key]}
            aria-invalid={
              settings[key] === '' ||
              !Number.isFinite(settings[key]) ||
              settings[key] < min ||
              settings[key] > max
            }
            onChange={(event) => {
              const value = event.target.value;
              setSettings({ ...settings, [key]: value === '' ? '' : Number(value) });
            }}
          />
        </label>
      ))}

      <button className="primary" onClick={saveSettings} disabled={!numbersValid}>
        Einstellungen speichern
      </button>
    </section>
  );
}
