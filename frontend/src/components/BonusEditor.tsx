import { useState } from 'react';
import type { TVStatus } from '../api';
import { BonusService } from '../services/BonusService';
import BonusWheel from './BonusWheel';
import BonusHistory from './BonusHistory';

type Props = {
  tvId: string;
  status?: TVStatus;
  minutes: number;
  onChange: (minutes: number) => void;
  canEdit: boolean;
  act: (action: () => Promise<unknown>) => Promise<void>;
};

export default function BonusEditor({ tvId, status, minutes, onChange, canEdit, act }: Props) {
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function grantBonus() {
    if (loading) return;
    setLoading(true);
    setError('');
    try {
      await act(async () => {
        try {
          const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60000).toISOString();
          await BonusService.grant(tvId, minutes, expiresAt);
          setRevision((value) => value + 1);
        } catch (reason) {
          setError((reason as Error).message);
          throw reason;
        }
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <BonusWheel minutes={minutes} onChange={onChange} disabled={!canEdit || loading} />
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <button
        disabled={!canEdit || !tvId || minutes < 1 || loading}
        className="primary"
        onClick={() => void grantBonus()}
      >
        {loading ? 'Wird gutgeschrieben…' : 'Bonus gutschreiben'}
      </button>
      <div className="note">
        Aktuelles Bonusguthaben: {Math.ceil((status?.bonus_remaining_seconds || 0) / 60)} Minuten
      </div>
      {tvId && (
        <BonusHistory
          key={tvId}
          tvId={tvId}
          canEdit={canEdit && !loading}
          revision={revision}
          onChange={async () => {
            await act(async () => undefined);
          }}
        />
      )}
    </>
  );
}
