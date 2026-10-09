import ScheduleExceptions from '../components/ScheduleExceptions';
import type { TV } from '../api';
import TVEditor from '../components/TVEditor';

type ScheduleViewProps = {
  tv?: TV;
  tvs: TV[];
  canEdit: boolean;
  onSelect: (id: string) => void;
  save: (body: TV) => void;
};

export default function ScheduleView({ tv, tvs, canEdit, onSelect, save }: ScheduleViewProps) {
  return (
    <section className="panel">
      <div className="section-title">
        <h2>Zeitplan & Limits</h2>
        <span className="muted">Pro Fernseher</span>
      </div>

      <TVEditor tv={tv} canEdit={canEdit} onSelect={onSelect} tvs={tvs} save={save} />
      {tv && <ScheduleExceptions tvId={tv.tv_id} canEdit={canEdit} />}
    </section>
  );
}
