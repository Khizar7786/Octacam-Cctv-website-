import { useEffect, useRef, useState } from "react";
import { promotionTiming } from "~/config/promotions";

/** Autoplay starts after hydration and is suspended when nobody can see the hero. */
export function usePromoPlayback(count: number, activeIndex: number, advance: () => void) {
  const sectionRef = useRef<HTMLElement>(null);
  const advanceRef = useRef(advance);
  const [motionAllowed, setMotionAllowed] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [visible, setVisible] = useState(false);
  const [inView, setInView] = useState(false);

  useEffect(() => { advanceRef.current = advance; }, [advance]);

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotion = () => setMotionAllowed(!preference.matches);
    const updateVisibility = () => setVisible(!document.hidden);
    updateMotion();
    updateVisibility();
    preference.addEventListener("change", updateMotion);
    document.addEventListener("visibilitychange", updateVisibility);
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.15 });
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => {
      preference.removeEventListener("change", updateMotion);
      document.removeEventListener("visibilitychange", updateVisibility);
      observer.disconnect();
    };
  }, []);

  const running = count > 1 && motionAllowed && visible && inView && !hovered && !focused;
  useEffect(() => {
    if (!running) return;
    // Restart the reading interval after any pause or manual selection.
    const timer = window.setTimeout(() => advanceRef.current(), promotionTiming.slideMs);
    return () => window.clearTimeout(timer);
  }, [running, activeIndex]);

  return { sectionRef, running, setFocused, setHovered };
}
