import { useEffect, useState } from 'react';
import { BonusService, type BonusGrant } from '../services/BonusService';

type Props = { tvId: string; canEdit: boolean; revision: number; onChange: () => Promise<void> };

export default function BonusHistory({ tvId, canEdit, revision, onChange }: Props) {
  const [grants, setGrants] = useState<BonusGrant[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!tvId) return;
    let active = true;
    BonusService.list(tvId)
      .then((items) => {
        if (active) {
          setGrants(items);
          setError('');
        }
      })
      .catch((reason) => {
        if (active) setError(String(reason));
      });
    return () => {
      active = false;
    };
  }, [tvId, revision]);

  async function revoke(id: number) {
    if (!window.confirm('Restliche Bonuszeit dieser Gutschrift entziehen?')) return;
    setBusy(true);
    try {
      await BonusService.revoke(tvId, id);
      setGrants(await BonusService.list(tvId));
      await onChange();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bonus-history">
      <h3>Bonusgutschriften</h3>
      {error && <p className="alert">{error}</p>}
      {grants.length === 0 && <p className="muted">Noch keine Bonusgutschriften.</p>}
      {grants.map((grant) => {
        const remaining = grant.granted_seconds - grant.consumed_seconds;
        const expired = Date.parse(grant.expires_at) <= Date.now();
        return (
          <div className="bonus-entry" key={grant.id}>
            <div>
              <strong>{Math.ceil(remaining / 60)} Min. übrig</strong>
              <div className="muted small">
                Vergeben: {Math.round(grant.granted_seconds / 60)} Min. ·
                {expired
                  ? ' Abgelaufen'
                  : ` Gültig bis ${new Date(grant.expires_at).toLocaleString('de-DE')}`}
              </div>
            </div>
            {canEdit && !expired && remaining > 0 && (
              <button className="secondary" disabled={busy} onClick={() => void revoke(grant.id)}>
                Entziehen
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
