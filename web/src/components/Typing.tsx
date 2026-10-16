import { useEffect, useRef, useState } from "react";
import { usePrefersReducedMotion } from "../state/useMediaQuery";
import "./Typing.css";

export interface TypingProps {
  text: string;
  charsPerSecond?: number;
  onDone?: () => void;
  className?: string;
}

/**
 * Reveals text with a typing effect. Assistive technology gets the whole text
 * at once; with reduced motion the text appears at once for everyone.
 */
export function Typing({ text, charsPerSecond = 60, onDone, className }: TypingProps) {
  const reduce = usePrefersReducedMotion();
  const [count, setCount] = useState(reduce ? text.length : 0);
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (reduce) {
      setCount(text.length);
      onDoneRef.current?.();
      return;
    }
    setCount(0);
    let shown = 0;
    const timer = window.setInterval(
      () => {
        shown += 1;
        setCount(shown);
        if (shown >= text.length) {
          window.clearInterval(timer);
          onDoneRef.current?.();
        }
      },
      Math.max(8, 1000 / charsPerSecond),
    );
    return () => window.clearInterval(timer);
  }, [text, charsPerSecond, reduce]);

  const done = count >= text.length;
  return (
    <span className={["typing", className].filter(Boolean).join(" ")}>
      <span className="visually-hidden">{text}</span>
      <span aria-hidden="true">{text.slice(0, count)}</span>
      {!done && <span aria-hidden="true" className="typing__caret" />}
    </span>
  );
}
