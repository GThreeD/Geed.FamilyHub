import { SettingsService } from '../services/SettingsService';

type SettingsViewProps = {
  settings: Record<string, any>;
  setSettings: (value: any) => void;
  act: (action: () => Promise<unknown>) => Promise<void>;
};

const NUMBER_SETTINGS = [
  'poll_seconds',
  'confirm_online_checks',
  'confirm_offline_checks',
  'cooldown_seconds',
  'power_hold_seconds',
];

export default function SettingsView({ settings, setSettings, act }: SettingsViewProps) {
  function saveSettings() {
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

      <label className="toggle">
        <input
          type="checkbox"
          checked={!!settings.armed}
          onChange={(event) => setSettings({ ...settings, armed: event.target.checked })}
        />
        Automatische Nachsperre aktivieren
      </label>

      {NUMBER_SETTINGS.map((key) => (
        <label key={key}>
          {key}
          <input
            type="number"
            value={settings[key]}
            step={key === 'power_hold_seconds' ? '0.5' : '1'}
            onChange={(event) => setSettings({ ...settings, [key]: Number(event.target.value) })}
          />
        </label>
      ))}

      <button className="primary" onClick={saveSettings}>
        Einstellungen speichern
      </button>
    </section>
  );
}
