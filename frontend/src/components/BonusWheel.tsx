import { useRef, useState, type PointerEvent, type KeyboardEvent } from 'react';

type BonusWheelProps = {
  minutes: number;
  onChange: (minutes: number) => void;
  disabled?: boolean;
};

const MINUTES_PER_REVOLUTION = 60;
const MAX_MINUTES = 12 * 60;
const RADIUS = 94;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function angleFromPointer(event: PointerEvent<SVGSVGElement>): number {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * 240 - 120;
  const y = ((event.clientY - rect.top) / rect.height) * 240 - 120;
  return Math.atan2(y, x);
}

function normalizeAngleDelta(delta: number): number {
  if (delta > Math.PI) return delta - 2 * Math.PI;
  if (delta < -Math.PI) return delta + 2 * Math.PI;
  return delta;
}

export default function BonusWheel({ minutes, onChange, disabled = false }: BonusWheelProps) {
  const drag = useRef<{ angle: number; value: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const minuteWithinRevolution = minutes % MINUTES_PER_REVOLUTION;
  const fraction = minuteWithinRevolution / MINUTES_PER_REVOLUTION;
  const angle = fraction * 2 * Math.PI - Math.PI / 2;
  const knobX = 120 + RADIUS * Math.cos(angle);
  const knobY = 120 + RADIUS * Math.sin(angle);
  const formattedTime = `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;

  function beginDrag(event: PointerEvent<SVGSVGElement>) {
    if (
      disabled ||
      !(event.target instanceof Element) ||
      !event.target.classList.contains('bonus-wheel-handle')
    )
      return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { angle: angleFromPointer(event), value: minutes };
    setDragging(true);
  }

  function moveDrag(event: PointerEvent<SVGSVGElement>) {
    if (!drag.current || disabled) return;
    const nextAngle = angleFromPointer(event);
    const delta = normalizeAngleDelta(nextAngle - drag.current.angle);
    // Store the unrounded fractional value, so tiny movements accumulate smoothly.
    const rawValue = Math.max(
      0,
      Math.min(MAX_MINUTES, drag.current.value + (delta / (2 * Math.PI)) * MINUTES_PER_REVOLUTION),
    );
    drag.current = { angle: nextAngle, value: rawValue };
    onChange(Math.round(rawValue));
  }

  function endDrag(event: PointerEvent<SVGSVGElement>) {
    drag.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function onKeyboard(event: KeyboardEvent<SVGSVGElement>) {
    if (disabled) return;
    const steps: Record<string, number> = {
      ArrowUp: 1,
      ArrowRight: 1,
      ArrowDown: -1,
      ArrowLeft: -1,
      PageUp: 15,
      PageDown: -15,
    };
    if (event.key in steps) {
      event.preventDefault();
      onChange(Math.min(MAX_MINUTES, Math.max(0, minutes + steps[event.key])));
    } else if (event.key === 'Home') {
      event.preventDefault();
      onChange(0);
    }
  }

  return (
    <div className="bonus-wheel-wrap">
      <svg
        className={`bonus-wheel${dragging ? ' dragging' : ''}`}
        viewBox="0 0 240 240"
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label="Bonuszeit in Minuten"
        aria-valuemin={0}
        aria-valuemax={MAX_MINUTES}
        aria-valuenow={minutes}
        aria-valuetext={`${Math.floor(minutes / 60)} Stunden und ${minutes % 60} Minuten`}
        aria-disabled={disabled}
        onPointerDown={beginDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onKeyDown={onKeyboard}
      >
        <circle cx="120" cy="120" r="109" className="bonus-wheel-background" />
        <circle cx="120" cy="120" r={RADIUS} className="bonus-wheel-track" />
        <circle
          cx="120"
          cy="120"
          r={RADIUS}
          className="bonus-wheel-progress"
          strokeDasharray={`${fraction * CIRCUMFERENCE} ${CIRCUMFERENCE}`}
          transform="rotate(-90 120 120)"
        />
        <circle cx={knobX} cy={knobY} r="11" className="bonus-wheel-handle" />
        <text x="120" y="101" className="bonus-wheel-label" textAnchor="middle">
          Bonuszeit
        </text>
        <text x="120" y="135" className="bonus-wheel-value" textAnchor="middle">
          {formattedTime}
        </text>
        <text x="120" y="155" className="bonus-wheel-label" textAnchor="middle">
          Stunden : Minuten
        </text>
      </svg>
      <p className="muted small bonus-wheel-help">
        Am Griff drehen · 1 Umdrehung = 1 Stunde · weiterdrehen für mehr
      </p>
    </div>
  );
}
