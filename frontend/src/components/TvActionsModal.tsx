import { useEffect, useState } from 'react';
import { Gift, Lock, LockOpen, Moon, ArrowLeft, X } from 'lucide-react';
import type { TV } from '../api';
import { DeviceService, type TvLock } from '../services/DeviceService';

type Props = {
  tv?: TV;
  canEdit: boolean;
  onClose: () => void;
  onBonus: (id: string) => void;
  act: (action: () => Promise<unknown>) => Promise<void>;
};

export default function TvActionsModal({ tv, canEdit, onClose, onBonus, act }: Props) {
  const [panel, setPanel] = useState<'choices' | 'lock'>('choices');
  const [lock, setLock] = useState<TvLock | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!tv || !canEdit) return;
    let cancelled = false;
    DeviceService.lock(tv.tv_id)
      .then((result) => {
        if (!cancelled) setLock(result.lock);
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, [tv?.tv_id, canEdit]);

  if (!tv) return null;

  async function updateLock(mode: 'until_tomorrow' | 'indefinite' | 'unlock') {
    if (!tv || loading) return;
    setLoading(true);
    setError('');
    try {
      await act(() =>
        mode === 'unlock' ? DeviceService.unlock(tv.tv_id) : DeviceService.setLock(tv.tv_id, mode),
      );
      const result = await DeviceService.lock(tv.tv_id);
      setLock(result.lock);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const status =
    lock?.mode === 'indefinite'
      ? 'Bis zur Freigabe gesperrt'
      : lock?.mode === 'until_tomorrow'
        ? 'Bis morgen gesperrt'
        : 'Keine manuelle Sperre';

  return (
    <div
      className="tv-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="tv-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tv-modal-title"
      >
        <div className="tv-modal-header">
          {panel === 'lock' && (
            <button
              className="tv-modal-icon"
              aria-label="Zurück"
              onClick={() => setPanel('choices')}
            >
              <ArrowLeft size={20} />
            </button>
          )}
          <div className="tv-modal-heading">
            <h2 id="tv-modal-title">{tv.name}</h2>
            <p className="muted small">
              {panel === 'choices' ? 'Was möchtest du machen?' : 'Manuelle Sperre'}
            </p>
          </div>
          <button className="tv-modal-icon" aria-label="Schließen" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {panel === 'choices' ? (
          <div className="tv-action-list">
            <button className="tv-action" disabled={!canEdit} onClick={() => onBonus(tv.tv_id)}>
              <span className="tv-action-symbol bonus">
                <Gift size={23} />
              </span>
              <span>
                <strong>Bonuszeit</strong>
                <small>Zusätzliche Minuten vergeben</small>
              </span>
              <span aria-hidden="true">→</span>
            </button>
            <button className="tv-action" disabled={!canEdit} onClick={() => setPanel('lock')}>
              <span className="tv-action-symbol lock">
                <Lock size={23} />
              </span>
              <span>
                <strong>Sperren</strong>
                <small>{status}</small>
              </span>
              <span aria-hidden="true">→</span>
            </button>
          </div>
        ) : (
          <div className="tv-lock-panel">
            <p className="tv-lock-status">{status}</p>
            {error && (
              <p className="alert" role="alert">
                {error}
              </p>
            )}
            <button
              className="tv-lock-option"
              disabled={loading}
              onClick={() => void updateLock('until_tomorrow')}
            >
              <Moon size={21} />
              <span>
                <strong>Bis morgen sperren</strong>
                <small>Automatische Freigabe um Mitternacht</small>
              </span>
            </button>
            <button
              className="tv-lock-option"
              disabled={loading}
              onClick={() => void updateLock('indefinite')}
            >
              <Lock size={21} />
              <span>
                <strong>Bis zur Freigabe sperren</strong>
                <small>Bleibt gesperrt, bis du freigibst</small>
              </span>
            </button>
            {lock && (
              <button
                className="tv-lock-option unlock"
                disabled={loading}
                onClick={() => void updateLock('unlock')}
              >
                <LockOpen size={21} />
                <span>
                  <strong>Sperre aufheben</strong>
                  <small>Normalen Zeitplan wieder nutzen</small>
                </span>
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
