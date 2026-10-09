import { useEffect, useState } from 'react';
import type { TV } from '../api';
import { DeviceService, type UsageStats } from '../services/DeviceService';

type Props = { tvs: TV[] };

export default function StatisticsView({ tvs }: Props) {
  const [stats, setStats] = useState<Record<string, UsageStats>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const ids = tvs.map((tv) => tv.tv_id).join('|');

  useEffect(() => {
    let active = true;
    Promise.allSettled(tvs.map((tv) => DeviceService.statistics(tv.tv_id))).then((results) => {
      if (!active) return;
      const next: Record<string, UsageStats> = {};
      const failures: Record<string, string> = {};
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') next[tvs[index].tv_id] = result.value;
        else failures[tvs[index].tv_id] = String(result.reason);
      });
      setStats(next);
      setErrors(failures);
    });
    return () => {
      active = false;
    };
  }, [ids]);

  return (
    <section className="panel">
      <h2>Nutzungsstatistiken</h2>
      {tvs.map((tv) => {
        const data = stats[tv.tv_id];
        return (
          <section key={tv.tv_id} className="stats-device">
            <h3>{tv.name}</h3>
            {errors[tv.tv_id] && <p className="alert">{errors[tv.tv_id]}</p>}
            {!data && !errors[tv.tv_id] && <p className="muted">Lade Statistik…</p>}
            {data && (
              <>
                <p className="muted">Erfasste Einschaltungen: {data.session_count}</p>
                <div className="tablewrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Tag</th>
                        <th>Minuten</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.days.map((day) => (
                        <tr key={day.day}>
                          <td>{day.day}</td>
                          <td>{Math.round(day.seconds / 60)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <details>
                  <summary>Einschaltungen ({data.sessions.length})</summary>
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
                        {data.sessions.map((session) => (
                          <tr key={session.id}>
                            <td>{new Date(session.started_at).toLocaleString('de-DE')}</td>
                            <td>
                              {session.ended_at
                                ? new Date(session.ended_at).toLocaleString('de-DE')
                                : 'Läuft'}
                            </td>
                            <td>{Math.round(session.duration_seconds / 60)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </>
            )}
          </section>
        );
      })}
    </section>
  );
}
