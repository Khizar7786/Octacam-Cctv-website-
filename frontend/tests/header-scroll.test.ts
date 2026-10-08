import assert from "node:assert/strict";
import test from "node:test";
import { initialHeaderScrollState, updateHeaderScroll } from "../app/lib/header-scroll.ts";

test("header leaves with the page before revealing on a deliberate upward scroll", () => {
  let state = initialHeaderScrollState();
  for (const y of [40, 120, 160]) {
    state = updateHeaderScroll(state, y, 160, false);
    assert.equal(state.mode, "flow");
  }
  state = updateHeaderScroll(state, 400, 160, false);
  assert.equal(state.mode, "hidden");
  for (const y of [398, 395, 390]) {
    state = updateHeaderScroll(state, y, 160, false);
    assert.equal(state.mode, "hidden");
  }
  state = updateHeaderScroll(state, 388, 160, false);
  assert.equal(state.mode, "visible");
  state = updateHeaderScroll(state, 20, 160, false);
  assert.equal(state.mode, "visible", "keep the revealed header pinned on the way to the top");
  assert.deepEqual(updateHeaderScroll(state, 0, 160, false), initialHeaderScrollState());
});

test("small direction reversals do not flicker the header", () => {
  let state = updateHeaderScroll(initialHeaderScrollState(), 600, 160, false);
  state = updateHeaderScroll(state, 580, 160, false);
  assert.equal(state.mode, "visible");
  for (const y of [581, 583, 579, 580, 584, 590]) {
    state = updateHeaderScroll(state, y, 160, false);
    assert.equal(state.mode, "visible");
  }
  state = updateHeaderScroll(state, 591, 160, false);
  assert.equal(state.mode, "hidden");
});

test("an open panel or focused header control remains visible during downward scrolling", () => {
  let state = updateHeaderScroll(initialHeaderScrollState(), 400, 160, false);
  state = updateHeaderScroll(state, 400, 160, true);
  assert.equal(state.mode, "visible", "focus reveals the header even without a scroll event");
  state = updateHeaderScroll(state, 700, 160, true);
  assert.equal(state.mode, "visible");
  state = updateHeaderScroll(state, 720, 160, false);
  assert.equal(state.mode, "hidden", "normal behavior resumes when interaction ends");
});

test("header height changes and restored scroll positions preserve natural scrolling", () => {
  let state = updateHeaderScroll(initialHeaderScrollState(), 300, 160, false);
  assert.equal(state.mode, "hidden", "a restored deep page does not force a reveal");
  state = updateHeaderScroll(state, 300, 360, false);
  assert.equal(state.mode, "flow", "wrapped navigation still scrolls out in full");
  assert.deepEqual(updateHeaderScroll(state, -30, 360, false), initialHeaderScrollState());
});
