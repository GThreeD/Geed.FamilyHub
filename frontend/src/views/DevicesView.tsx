import { useState } from 'react';
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
      tv_id: id,
      name,
      ip,
      enabled: true,
      timezone: 'Europe/Berlin',
      daily_limit_minutes: null,
      weekly_limit_minutes: null,
      schedule: Object.fromEntries(DAYS.map((day) => [day, []])),
    };
    void act(() => DeviceService.create(tv));
  }

  return (
    <section className="panel desktop-admin">
      <h2>Fernseher verwalten</h2>
      <div className="device-fields">
        <label>
          ID
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="kinderzimmer" />
        </label>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          IP-Adresse
          <input value={ip} onChange={(e) => setIp(e.target.value)} placeholder="192.168.3.86" />
        </label>
        <button className="primary" onClick={create}>
          Gerät hinzufügen
        </button>
      </div>
      {tvs.map((tv) => {
        const value = editing[tv.tv_id] ?? { name: tv.name, ip: tv.ip };
        const change = (field: 'name' | 'ip', val: string) =>
          setEditing((old) => ({ ...old, [tv.tv_id]: { ...value, [field]: val } }));
        return (
          <div key={tv.tv_id} className="device-row">
            <strong>{tv.tv_id}</strong>
            <input
              aria-label="Gerätename"
              value={value.name}
              onChange={(e) => change('name', e.target.value)}
            />
            <input
              aria-label="IP-Adresse"
              value={value.ip}
              onChange={(e) => change('ip', e.target.value)}
            />
            <button className="primary" onClick={() => void act(() => TvService.update({ ...tv, ...value }))}>
              Speichern
            </button>
            <button
              className="secondary"
              onClick={() => {
                if (window.confirm(`Gerät ${tv.name} samt Nutzungsdaten löschen?`)) {
                  void act(() => DeviceService.remove(tv.tv_id));
                }
              }}
            >
              Löschen
            </button>
          </div>
        );
      })}
    </section>
  );
}
