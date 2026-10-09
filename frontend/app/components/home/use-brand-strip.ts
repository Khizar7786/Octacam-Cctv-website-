import { useEffect, useRef, useState } from "react";

/** Native scrolling keeps every real link reachable by keyboard and touch. */
export function useBrandStrip(brandCount: number) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const groupRef = useRef<HTMLUListElement>(null);
  const [motionAllowed, setMotionAllowed] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [geometry, setGeometry] = useState({ width: 0, copies: 1, speed: 24 });
  const enabled = motionAllowed && brandCount > 1;

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setMotionAllowed(!preference.matches);
    update();
    preference.addEventListener("change", update);
    return () => preference.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    const group = groupRef.current;
    if (!enabled || !viewport || !group) return;
    const measure = () => {
      const width = group.getBoundingClientRect().width;
      const token = Number(getComputedStyle(viewport).getPropertyValue("--brand-strip-speed"));
      const speed = Number.isFinite(token) && token > 0 ? token : 24;
      const copies = width > 0 ? Math.max(1, Math.ceil(viewport.clientWidth / width)) : 1;
      setGeometry((current) => current.width === width && current.copies === copies && current.speed === speed ? current : { width, copies, speed });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(viewport);
    observer.observe(group);
    return () => observer.disconnect();
  }, [enabled, brandCount]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!enabled || hovered || focused || geometry.width === 0 || !viewport) return;
    let frame = 0;
    let inView = true;
    let previousTime: number | null = null;
    // Accumulate fractions separately: browsers can round scrollLeft assignments.
    let position = viewport.scrollLeft % geometry.width;
    const tick = (time: number) => {
      if (previousTime !== null) {
        const elapsed = Math.min(time - previousTime, 64);
        position = (position + geometry.speed * elapsed / 1000) % geometry.width;
        viewport.scrollLeft = position;
      }
      previousTime = time;
      frame = requestAnimationFrame(tick);
    };
    const updateVisibility = () => {
      cancelAnimationFrame(frame);
      previousTime = null;
      if (!document.hidden && inView) frame = requestAnimationFrame(tick);
    };
    const observer = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      updateVisibility();
    });
    observer.observe(viewport);
    updateVisibility();
    document.addEventListener("visibilitychange", updateVisibility);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", updateVisibility);
    };
  }, [enabled, hovered, focused, geometry]);

  return { viewportRef, groupRef, enabled, copies: geometry.copies, setHovered, setFocused };
}
