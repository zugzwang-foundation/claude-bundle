import { useId } from "react";
import "./Clock.css";

export interface ClockProps {
  /** How far time has passed, 0 to 1. Drives the hands and the progress ring. */
  progress: number;
  /** Full turns the hour hand makes from start to finish. The minute hand turns four times as fast. */
  turns?: number;
  /** A caption under the dial, e.g. the current month. It flips in whenever it changes. */
  label?: string;
  /** What the clock stands for, read out to assistive technology. */
  description: string;
  /** Width and height in CSS pixels. */
  size?: number;
  className?: string;
}

const TICK_ANGLES = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330];
/** Circumference of the progress ring (r = 46). */
const RING = 2 * Math.PI * 46;

function clamp01(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

/**
 * A simple analogue clock drawn in SVG. The parent drives it: pass a rising
 * `progress` and the hands turn, the ring fills and the label flips.
 * With prefers-reduced-motion the parent passes 1 straight away.
 */
export function Clock({
  progress,
  turns = 3,
  label,
  description,
  size = 220,
  className,
}: ClockProps) {
  const titleId = useId();
  const p = clamp01(progress);
  const hour = p * turns * 360;
  const minute = hour * 4;
  const classes = ["clock", className].filter(Boolean).join(" ");

  return (
    <figure className={classes} style={{ width: size }}>
      <svg
        className="clock__dial"
        viewBox="0 0 100 100"
        width={size}
        height={size}
        role="img"
        aria-labelledby={titleId}
      >
        <title id={titleId}>{description}</title>
        <circle className="clock__face" cx="50" cy="50" r="46" />
        <circle
          className="clock__ring"
          cx="50"
          cy="50"
          r="46"
          strokeDasharray={RING}
          strokeDashoffset={RING * (1 - p)}
          transform="rotate(-90 50 50)"
        />
        {TICK_ANGLES.map((angle) => {
          const major = angle % 90 === 0;
          return (
            <line
              key={angle}
              className={major ? "clock__tick clock__tick--major" : "clock__tick"}
              x1="50"
              y1="8"
              x2="50"
              y2={major ? 14 : 11}
              transform={`rotate(${angle} 50 50)`}
            />
          );
        })}
        <line
          className="clock__hand clock__hand--hour"
          x1="50"
          y1="54"
          x2="50"
          y2="28"
          transform={`rotate(${hour} 50 50)`}
        />
        <line
          className="clock__hand clock__hand--minute"
          x1="50"
          y1="55"
          x2="50"
          y2="17"
          transform={`rotate(${minute} 50 50)`}
        />
        <circle className="clock__pin" cx="50" cy="50" r="2.8" />
      </svg>
      {label ? (
        <figcaption className="clock__label" aria-hidden="true">
          <span key={label} className="clock__month">
            {label}
          </span>
        </figcaption>
      ) : null}
    </figure>
  );
}
