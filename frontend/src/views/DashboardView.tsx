import { Tv } from 'lucide-react';
import type { TV, TVStatus } from '../api';

type DashboardViewProps = {
  tvs: TV[];
  status: Record<string, TVStatus>;
  onSelectTv: (id: string) => void;
};

export default function DashboardView({ tvs, status, onSelectTv }: DashboardViewProps) {
  const observations = Object.values(status);
  const onlineCount = observations.filter(
    (entry) => entry.online_observation?.confirmed_online,
  ).length;
  const blockedCount = observations.filter((entry) => !entry.allowed).length;

  return (
    <>
      <div className="stats">
        <div className="stat">
          <span>Fernseher</span>
          <strong>{tvs.length}</strong>
          <small>Verwaltete Geräte</small>
        </div>
        <div className="stat">
          <span>Online erkannt</span>
          <strong>{onlineCount}</strong>
          <small>Lokale Port-Prüfung</small>
        </div>
        <div className="stat">
          <span>Aktive Sperren</span>
          <strong>{blockedCount}</strong>
          <small>Außerhalb erlaubter Nutzung</small>
        </div>
      </div>

      <h2>Deine Fernseher</h2>
      <div className="tv-grid">
        {tvs.map((tv) => {
          const current = status[tv.tv_id];
          const online = current?.online_observation?.state || 'unknown';
          const usedSeconds = current?.used_today_seconds || 0;
          const dailyLimit = tv.daily_limit_minutes || 0;
          const usagePercent = dailyLimit
            ? Math.min(100, (usedSeconds / (dailyLimit * 60)) * 100)
            : 0;
          const onlineLabel =
            online === 'online' ? 'Online' : online === 'offline' ? 'Offline' : 'Unbekannt';

          return (
            <article
              className="tv-card tv-card-action"
              key={tv.tv_id}
              role="button"
              tabIndex={0}
              aria-label={`${tv.name}: Aktionen öffnen`}
              onClick={() => onSelectTv(tv.tv_id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelectTv(tv.tv_id);
                }
              }}
            >
              <div className="tv-heading">
                <div className="tv-icon">
                  <Tv />
                </div>
                <span className={'pill ' + (online === 'online' ? 'green' : '')}>
                  {onlineLabel}
                </span>
              </div>

              <h3>{tv.name}</h3>
              <p className="muted small">
                {tv.ip} · {tv.enabled ? 'Aktiv' : 'Deaktiviert'}
              </p>

              <div className="usage-head">
                <span>Heute genutzt</span>
                <strong>
                  {Math.floor(usedSeconds / 60)} min {dailyLimit ? `/ ${dailyLimit} min` : ''}
                </strong>
              </div>
              <div className="bar">
                <span style={{ width: `${usagePercent}%` }} />
              </div>

              <div className="card-foot">
                <span>{current?.allowed ? 'Nutzung erlaubt' : 'Aktuell gesperrt'}</span>
                <span className="link">Aktionen →</span>
              </div>
            </article>
          );
        })}

        {!tvs.length && (
          <div className="empty">
            Noch keine TVs in der Datenbank. Es sind noch keine TV-Datensätze hinterlegt. Die
            Einrichtung eines neuen Gerätes ergänzen wir in einem Folgepatch.
          </div>
        )}
      </div>
    </>
  );
}
