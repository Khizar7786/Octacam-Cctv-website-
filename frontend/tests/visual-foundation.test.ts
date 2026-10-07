import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const tokens = readFileSync(`${frontendRoot}/app/styles/tokens.css`, "utf8");

function colorToken(name: string): string {
  const match = tokens.match(new RegExp(`--${name}:\\s*([^;]+);`));
  assert.ok(match, `Expected a color token named --${name}`);
  const value = match[1].trim();
  const alias = value.match(/^var\(--([\w-]+)\)$/);
  if (alias) return colorToken(alias[1]);
  assert.match(value, /^#[0-9a-fA-F]{6}$/, `Expected a six-digit color value for --${name}`);
  return value;
}

function relativeLuminance(hex: string) {
  const channels = [1, 3, 5].map((start) => Number.parseInt(hex.slice(start, start + 2), 16) / 255);
  const linear = channels.map((channel) => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(foreground: string, background: string) {
  const light = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const dark = Math.min(relativeLuminance(foreground), relativeLuminance(background));
  return (light + 0.05) / (dark + 0.05);
}

test("public logo preserves the approved RGBA master", () => {
  const source = readFileSync(`${repositoryRoot}/Logo/OctacamLogo.png`);
  const publicAsset = readFileSync(`${frontendRoot}/public/brand/octacam-logo.png`);

  assert.deepEqual(publicAsset, source);
  assert.equal(publicAsset.toString("ascii", 1, 4), "PNG");
  assert.equal(publicAsset.readUInt32BE(16), 1254);
  assert.equal(publicAsset.readUInt32BE(20), 1254);
  assert.equal(publicAsset[25], 6, "PNG color type 6 retains the alpha channel");
});

test("text and focus color pairs meet their WCAG contrast targets", () => {
  const pairs = [
    ["brand", "brand-foreground", 4.5],
    ["foreground", "background", 4.5],
    ["muted-foreground", "card", 4.5],
    ["info", "info-surface", 4.5],
    ["success", "success-surface", 4.5],
    ["warning", "warning-surface", 4.5],
    ["error", "error-surface", 4.5],
    ["brand", "background", 3],
    ["navigation-foreground", "header-strip", 4.5],
    ["navigation-foreground", "navigation", 4.5],
    ["navigation-foreground", "navigation-hover", 4.5],
    ["navigation-focus", "navigation", 3],
    ["navigation-focus", "navigation-hover", 3],
    ["footer-foreground", "footer", 4.5],
    ["footer-muted", "footer", 4.5],
    ["navigation-focus", "footer", 3],
  ] as const;

  for (const [foreground, background, minimum] of pairs) {
    const ratio = contrastRatio(colorToken(foreground), colorToken(background));
    assert.ok(ratio >= minimum, `${foreground} on ${background} is ${ratio.toFixed(2)}:1`);
  }
});
