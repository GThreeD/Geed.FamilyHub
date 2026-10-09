import { useState } from 'react';
import { Plus, Save, Trash2, Tv2 } from 'lucide-react';
import type { TV } from '../api';
import { DeviceService } from '../services/DeviceService';
import { TvService } from '../services/TvService';

type Props = { tvs: TV[]; act: (action: () => Promise<unknown>) => Promise<void> };
const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

export default function DevicesView({ tvs, act }: Props) {
  const [name, setName] = useState('');
  const [ip, setIp] = useState('');
  const [id, setId] = useState('');
  const [editing, setEditing] = useState<Record<string, { name: string; ip: string }>>({});

  function create() {
    const tv: TV = {
      tv_id: id.trim(),
      name: name.trim(),
      ip: ip.trim(),
      enabled: true,
      timezone: 'Europe/Berlin',
      daily_limit_minutes: null,
      weekly_limit_minutes: null,
      schedule: Object.fromEntries(DAYS.map((day) => [day, []])),
    };
    void act(() => DeviceService.create(tv));
  }

  return (
    <div className="devices-layout">
      <section className="panel device-create-panel">
        <div className="device-section-heading">
          <span className="device-heading-icon">
            <Plus size={20} />
          </span>
          <div>
            <h2>Gerät hinzufügen</h2>
            <p>Neuen Fernseher mit seiner Netzwerkadresse anlegen.</p>
          </div>
        </div>
        <div className="device-create-fields">
          <label>
            Geräte-ID
            <input value={id} onChange={(e) => setId(e.target.value)} placeholder="kinderzimmer" />
          </label>
          <label>
            Anzeigename
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Kinderzimmer TV"
            />
          </label>
          <label>
            IP-Adresse
            <input value={ip} onChange={(e) => setIp(e.target.value)} placeholder="192.168.3.86" />
          </label>
        </div>
        <button className="primary device-add-button" type="button" onClick={create}>
          <Plus size={17} /> Gerät hinzufügen
        </button>
      </section>

      <section className="device-list-section" aria-label="Vorhandene Fernseher">
        <div className="device-list-heading">
          <h2>Vorhandene Geräte</h2>
          <span>
            {tvs.length} {tvs.length === 1 ? 'Fernseher' : 'Fernseher'}
          </span>
        </div>
        {tvs.length === 0 && (
          <div className="panel device-empty">Noch keine Fernseher eingerichtet.</div>
        )}
        <div className="device-card-list">
          {tvs.map((tv) => {
            const value = editing[tv.tv_id] ?? { name: tv.name, ip: tv.ip };
            const change = (field: 'name' | 'ip', val: string) =>
              setEditing((old) => ({ ...old, [tv.tv_id]: { ...value, [field]: val } }));
            const changed = value.name !== tv.name || value.ip !== tv.ip;
            return (
              <article key={tv.tv_id} className="panel device-card">
                <div className="device-card-heading">
                  <span className="device-heading-icon">
                    <Tv2 size={20} />
                  </span>
                  <div className="device-card-title">
                    <h3>{tv.name || tv.tv_id}</h3>
                    <small>ID: {tv.tv_id}</small>
                  </div>
                  <div className="device-card-actions">
                    <button
                      type="button"
                      className="device-icon-button device-save-button"
                      aria-label={`${tv.name || tv.tv_id} speichern`}
                      title="Änderungen speichern"
                      disabled={!changed}
                      onClick={() => void act(() => TvService.update({ ...tv, ...value }))}
                    >
                      <Save size={19} />
                    </button>
                    <button
                      type="button"
                      className="device-icon-button device-delete-button"
                      aria-label={`${tv.name || tv.tv_id} löschen`}
                      title="Fernseher löschen"
                      onClick={() => {
                        if (window.confirm(`Gerät ${tv.name} samt Nutzungsdaten löschen?`)) {
                          void act(() => DeviceService.remove(tv.tv_id));
                        }
                      }}
                    >
                      <Trash2 size={19} />
                    </button>
                  </div>
                </div>
                <div className="device-edit-fields">
                  <label>
                    Anzeigename
                    <input value={value.name} onChange={(e) => change('name', e.target.value)} />
                  </label>
                  <label>
                    IP-Adresse
                    <input value={value.ip} onChange={(e) => change('ip', e.target.value)} />
                  </label>
                </div>
                {changed && <p className="device-unsaved">Ungespeicherte Änderungen</p>}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
