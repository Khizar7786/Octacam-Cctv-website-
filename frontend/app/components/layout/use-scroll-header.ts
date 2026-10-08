import { useEffect, useRef, useState } from "react";
import { initialHeaderScrollState, updateHeaderScroll, type HeaderScrollMode } from "~/lib/header-scroll";

export function useScrollHeader(panelOpen: boolean) {
  const headerRef = useRef<HTMLElement>(null);
  const updateRef = useRef<(() => void) | null>(null);
  const panelOpenRef = useRef(panelOpen);
  const [mode, setMode] = useState<HeaderScrollMode>("flow");

  useEffect(() => {
    panelOpenRef.current = panelOpen;
    updateRef.current?.();
  }, [panelOpen]);

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;

    let state = initialHeaderScrollState();
    let frame = 0;
    let height = header.offsetHeight;
    const root = document.documentElement;

    function update() {
      frame = 0;
      // Ignore elastic overscroll at both ends of a mobile page.
      const maxY = Math.max(0, root.scrollHeight - window.innerHeight);
      const y = Math.min(maxY, Math.max(0, window.scrollY));
      const next = updateHeaderScroll(state, y, height, panelOpenRef.current || header!.contains(document.activeElement));
      if (next.mode !== state.mode) setMode(next.mode);
      state = next;
    }

    function scheduleUpdate() {
      if (!frame) frame = window.requestAnimationFrame(update);
    }

    function measure() {
      height = header!.offsetHeight;
      root.style.setProperty("--site-header-height", `${height}px`);
      scheduleUpdate();
    }

    measure();
    updateRef.current = scheduleUpdate;
    const observer = new ResizeObserver(measure);
    observer.observe(header);
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    header.addEventListener("focusin", scheduleUpdate);
    header.addEventListener("focusout", scheduleUpdate);

    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", scheduleUpdate);
      window.removeEventListener("resize", scheduleUpdate);
      header.removeEventListener("focusin", scheduleUpdate);
      header.removeEventListener("focusout", scheduleUpdate);
      root.style.removeProperty("--site-header-height");
      updateRef.current = null;
    };
  }, []);

  return { headerRef, mode };
}
