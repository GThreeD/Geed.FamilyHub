import { useRef, useState, type PointerEvent } from 'react';

type PatternProps = {
  value: string;
  onChange: (next: string) => void;
  onComplete?: (finalValue: string) => void;
  disabled?: boolean;
};

const POINTS = Array.from({ length: 9 }, (_, id) => ({
  id: id + 1,
  x: 15 + (id % 3) * 35,
  y: 15 + Math.floor(id / 3) * 35,
}));

export default function Pattern({ value, onChange, onComplete, disabled }: PatternProps) {
  const [drawing, setDrawing] = useState(false);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  const root = useRef<SVGSVGElement>(null);
  const path = useRef('');

  function location(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) * 100) / rect.width,
      y: ((event.clientY - rect.top) * 100) / rect.height,
    };
  }

  function addPoint(pos: { x: number; y: number }) {
    const hit = POINTS.find((dot) => Math.hypot(dot.x - pos.x, dot.y - pos.y) < 12);
    if (!hit || path.current.includes(String(hit.id))) return;
    path.current += hit.id;
    onChange(path.current);
  }

  function begin(event: PointerEvent<SVGSVGElement>) {
    if (disabled) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    path.current = '';
    onChange('');
    setDrawing(true);
    const pos = location(event);
    setPointer(pos);
    addPoint(pos);
  }

  function move(event: PointerEvent<SVGSVGElement>) {
    if (!drawing || disabled) return;
    const pos = location(event);
    setPointer(pos);
    addPoint(pos);
  }

  function finish() {
    if (!drawing) return;
    setDrawing(false);
    setPointer(null);
    if (path.current.length >= 6) onComplete?.(path.current);
  }

  const selected = value
    .split('')
    .map((n) => POINTS[Number(n) - 1])
    .filter((point): point is (typeof POINTS)[number] => Boolean(point));
  const line = selected.map((point) => `${point.x},${point.y}`).join(' ');

  return (
    <div className="pattern-container">
      <svg
        ref={root}
        className="pattern-svg"
        viewBox="0 0 100 100"
        role="group"
        aria-label="Entsperrmuster: mit Finger oder Maus mindestens sechs Punkte verbinden"
        onPointerDown={begin}
        onPointerMove={move}
        onPointerUp={finish}
        onPointerCancel={finish}
        style={{ touchAction: 'none' }}
      >
        <polyline className="pattern-trace" points={line} />
        {drawing && pointer && selected.length > 0 && (
          <line
            className="pattern-trace active"
            x1={selected[selected.length - 1].x}
            y1={selected[selected.length - 1].y}
            x2={pointer.x}
            y2={pointer.y}
          />
        )}
        {POINTS.map((dot) => (
          <circle
            key={dot.id}
            cx={dot.x}
            cy={dot.y}
            r="5"
            className={value.includes(String(dot.id)) ? 'pattern-point selected' : 'pattern-point'}
          />
        ))}
      </svg>
      <button
        className="link"
        type="button"
        onClick={() => {
          path.current = '';
          onChange('');
        }}
      >
        Muster zurücksetzen
      </button>
    </div>
  );
}
