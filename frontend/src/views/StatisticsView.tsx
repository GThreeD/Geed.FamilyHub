import { useEffect, useState } from 'react';
import type { TV } from '../api';
import { DeviceService, type UsageStats } from '../services/DeviceService';

type Props = { tvs: TV[] };
export default function StatisticsView({ tvs }: Props) {
  const [selected, setSelected] = useState('');
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [error, setError] = useState('');
  const id = tvs.some((tv) => tv.tv_id === selected) ? selected : tvs[0]?.tv_id;

  useEffect(() => {
    if (!id) return;
    DeviceService.statistics(id)
      .then((value) => {
        setStats(value);
        setError('');
      })
      .catch((reason) => setError(String(reason)));
  }, [id]);

  return (
    <section className="panel">
      <h2>Nutzungsstatistiken</h2>
      <label>
        Fernseher
        <select value={id ?? ''} onChange={(event) => setSelected(event.target.value)}>
          {tvs.map((tv) => (
            <option key={tv.tv_id} value={tv.tv_id}>
              {tv.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="alert">{error}</p>}
      <h3>Verlauf nach Tagen</h3>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Tag</th>
              <th>Minuten</th>
            </tr>
          </thead>
          <tbody>
            {stats?.days.map((day) => (
              <tr key={day.day}>
                <td>{day.day}</td>
                <td>{Math.round(day.seconds / 60)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Erfasste Einschaltungen (seit v2.5)</h3>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Beginn</th>
              <th>Ende</th>
              <th>Minuten</th>
            </tr>
          </thead>
          <tbody>
            {stats?.sessions.map((session) => (
              <tr key={session.id}>
                <td>{new Date(session.started_at).toLocaleString('de-DE')}</td>
                <td>
                  {session.ended_at ? new Date(session.ended_at).toLocaleString('de-DE') : 'Läuft'}
                </td>
                <td>{Math.round(session.duration_seconds / 60)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
