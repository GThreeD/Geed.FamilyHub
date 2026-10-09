import { useEffect, useState } from 'react';
import {
  ScheduleExceptionService,
  type ScheduleException,
} from '../services/ScheduleExceptionService';

type Props = { tvId: string; canEdit: boolean };

export default function ScheduleExceptions({ tvId, canEdit }: Props) {
  const [items, setItems] = useState<ScheduleException[]>([]);
  const [name, setName] = useState('Ferien');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [from, setFrom] = useState('09:00');
  const [to, setTo] = useState('21:00');
  const [error, setError] = useState('');

  async function load() {
    if (tvId) setItems(await ScheduleExceptionService.list(tvId));
  }

  useEffect(() => {
    setItems([]);
    void load().catch((err: Error) => setError(err.message));
  }, [tvId]);

  async function create() {
    setError('');
    try {
      await ScheduleExceptionService.create(tvId, {
        name,
        start_date: start,
        end_date: end,
        windows: [[from, to]],
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: number) {
    setError('');
    try {
      await ScheduleExceptionService.remove(tvId, id);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="exceptions">
      <h3>Ferien & Ausnahmen</h3>
      {items.map((item) => (
        <div className="exception-item" key={item.id}>
          <div>
            <strong>{item.name}</strong>
            <small>
              {item.start_date} – {item.end_date}
            </small>
            <small>{item.windows.map(([a, b]) => `${a}–${b}`).join(', ') || 'Gesperrt'}</small>
          </div>
          {canEdit && (
            <button className="link" onClick={() => void remove(item.id)}>
              Löschen
            </button>
          )}
        </div>
      ))}
      {canEdit && (
        <div className="exception-editor">
          <label>
            Name
            <input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Von
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            Bis
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <label>
            Start
            <input type="time" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label>
            Ende
            <input type="time" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
          <button
            type="button"
            className="primary"
            disabled={!start || !end}
            onClick={() => void create()}
          >
            Ausnahme speichern
          </button>
        </div>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
