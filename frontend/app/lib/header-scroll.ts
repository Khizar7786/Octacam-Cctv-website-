export type HeaderScrollMode = "flow" | "hidden" | "visible";

export type HeaderScrollState = {
  mode: HeaderScrollMode;
  previousY: number;
  direction: "up" | "down" | null;
  directionStart: number;
};

export function initialHeaderScrollState(): HeaderScrollState {
  return { mode: "flow", previousY: 0, direction: null, directionStart: 0 };
}

export function updateHeaderScroll(
  state: HeaderScrollState,
  y: number,
  headerHeight: number,
  keepVisible: boolean,
): HeaderScrollState {
  y = Math.max(0, y);
  if (y === 0) return initialHeaderScrollState();

  const direction = y === state.previousY ? state.direction : y > state.previousY ? "down" : "up";
  const directionStart = direction === state.direction ? state.directionStart : state.previousY;
  // Accumulate small movements in the same direction without reacting to scroll jitter.
  const deliberateScroll = Math.abs(y - directionStart) >= 12;
  let mode = state.mode;

  if (keepVisible) {
    mode = "visible";
  } else if (mode === "visible") {
    if (y > headerHeight && direction === "down" && deliberateScroll) mode = "hidden";
  } else if (y <= headerHeight) {
    mode = "flow";
  } else {
    mode = direction === "up" && deliberateScroll ? "visible" : "hidden";
  }

  return { mode, previousY: y, direction, directionStart };
}
