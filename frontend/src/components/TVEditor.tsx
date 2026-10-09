import { useState, useEffect } from 'react';
import type { TV } from '../api';

const days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const labels = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

export default function TVEditor({
  tv,
  tvs,
  onSelect,
  canEdit,
  save,
}: {
  tv?: TV;
  tvs: TV[];
  onSelect: (s: string) => void;
  canEdit: boolean;
  save: (s: TV) => void;
}) {
  const [draft, D] = useState<TV | null>(null);
  useEffect(() => D(tv ? structuredClone(tv) : null), [tv?.tv_id]);
  function change(k: keyof TV, v: any) {
    D((old) => (old ? { ...old, [k]: v } : old));
  }
  function windowEdit(day: string, idx: number, key: number, value: string) {
    D((old) => {
      if (!old) return old;
      const s = structuredClone(old.schedule);
      s[day][idx][key] = value;
      return { ...old, schedule: s };
    });
  }
  return (
    <>
      <label>
        TV
        <select value={tv?.tv_id || ''} onChange={(e) => onSelect(e.target.value)}>
          {tvs.map((t) => (
            <option key={t.tv_id} value={t.tv_id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>
      {draft && (
        <>
          <div className="fields">
            <label>
              Tageslimit (Minuten)
              <input
                disabled={!canEdit}
                type="number"
                min="1"
                value={draft.daily_limit_minutes ?? ''}
                onChange={(e) =>
                  change('daily_limit_minutes', e.target.value === '' ? null : +e.target.value)
                }
              />
            </label>
            <label>
              Wochenlimit (Minuten)
              <input
                disabled={!canEdit}
                type="number"
                min="1"
                value={draft.weekly_limit_minutes ?? ''}
                onChange={(e) =>
                  change('weekly_limit_minutes', e.target.value === '' ? null : +e.target.value)
                }
              />
            </label>
          </div>
          <div className="week">
            {days.map((day, i) => (
              <div className="day" key={day}>
                <strong>{labels[i]}</strong>
                <div className="window-list">
                  {(draft.schedule[day] || []).map((window, j) => (
                    <div className="window" key={j}>
                      <input
                        aria-label="Start"
                        type="time"
                        disabled={!canEdit}
                        value={window[0]}
                        onChange={(e) => windowEdit(day, j, 0, e.target.value)}
                      />
                      <span>–</span>
                      <input
                        aria-label="Ende"
                        type="time"
                        disabled={!canEdit}
                        value={window[1]}
                        onChange={(e) => windowEdit(day, j, 1, e.target.value)}
                      />
                      {canEdit && (
                        <button
                          className="icon-button"
                          onClick={() =>
                            D((old) => {
                              if (!old) return old;
                              const s = structuredClone(old.schedule);
                              s[day].splice(j, 1);
                              return { ...old, schedule: s };
                            })
                          }
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {canEdit && (
                  <button
                    className="link"
                    onClick={() =>
                      D((old) => {
                        if (!old) return old;
                        const s = structuredClone(old.schedule);
                        s[day].push(['15:00', '20:00']);
                        s[day].sort((a, b) => a[0].localeCompare(b[0]));
                        return { ...old, schedule: s };
                      })
                    }
                  >
                    + Zeitfenster
                  </button>
                )}
              </div>
            ))}
          </div>
          {canEdit && (
            <button className="primary" onClick={() => save(draft)}>
              Zeitplan speichern
            </button>
          )}
        </>
      )}
    </>
  );
}
