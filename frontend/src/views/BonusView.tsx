import type { TV, TVStatus } from '../api';
import BonusEditor from '../components/BonusEditor';

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

      <BonusEditor
        tvId={selected}
        status={status[selected]}
        minutes={bonus}
        onChange={setBonus}
        canEdit={canEdit}
        act={act}
      />
    </section>
  );
}
