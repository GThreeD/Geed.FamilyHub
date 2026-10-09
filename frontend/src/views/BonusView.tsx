import { useState } from 'react';
import BonusHistory from '../components/BonusHistory';
import type { TV, TVStatus } from '../api';
import { BonusService } from '../services/BonusService';
import BonusWheel from '../components/BonusWheel';

type BonusViewProps = {
  tvs: TV[];
  status: Record<string, TVStatus>;
  selected: string;
  setSelected: (id: string) => void;
  bonus: number;
  setBonus: (minutes: number) => void;
  canEdit: boolean;
  act: (action: () => Promise<unknown>) => Promise<void>;
};

export default function BonusView({
  tvs,
  status,
  selected,
  setSelected,
  bonus,
  setBonus,
  canEdit,
  act,
}: BonusViewProps) {
  const [revision, setRevision] = useState(0);
  const remainingMinutes = Math.round((status[selected]?.bonus_remaining_seconds || 0) / 60);

  function grantBonus() {
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60000).toISOString();
    void act(() => BonusService.grant(selected, bonus, expiresAt)).then(() =>
      setRevision((v) => v + 1),
    );
  }

  return (
    <section className="panel narrow">
      <h2>Bonuszeit gewähren</h2>

      <label>
        Fernseher
        <select value={selected} onChange={(event) => setSelected(event.target.value)}>
          {tvs.map((tv) => (
            <option key={tv.tv_id} value={tv.tv_id}>
              {tv.name}
            </option>
          ))}
        </select>
      </label>

      <BonusWheel minutes={bonus} onChange={setBonus} disabled={!canEdit} />

      <button
        disabled={!canEdit || !selected || bonus < 1}
        className="primary"
        onClick={grantBonus}
      >
        Bonus gutschreiben
      </button>

      <div className="note">Aktuelles Bonusguthaben: {remainingMinutes} Minuten</div>
      {selected && (
        <BonusHistory
          tvId={selected}
          canEdit={canEdit}
          revision={revision}
          onChange={async () => {
            await act(async () => undefined);
          }}
        />
      )}
    </section>
  );
}
