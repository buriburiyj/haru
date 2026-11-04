// Appearance settings (theme, font size) kept in localStorage. No server needed.
export type Theme = "system" | "light" | "dark";
export type FontSize = "small" | "medium" | "large";
export type Font = "default" | "gothic" | "system"; // 기본(답변 명조) / 고딕 / 시스템

export const THEMES: Theme[] = ["system", "light", "dark"];
export const FONT_SIZES: FontSize[] = ["small", "medium", "large"];
export const FONTS: Font[] = ["default", "gothic", "system"];

const KEYS = { theme: "haru.theme", fontSize: "haru.fontSize", font: "haru.font" } as const;

function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return (allowed as readonly string[]).includes(v ?? "") ? (v as T) : fallback;
  } catch {
    return fallback; // storage can be blocked (private mode); the setting then lasts only for this session
  }
}
function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export const getTheme = () => read<Theme>(KEYS.theme, THEMES, "system");
export const getFontSize = () => read<FontSize>(KEYS.fontSize, FONT_SIZES, "medium");
export const getFont = () => read<Font>(KEYS.font, FONTS, "default");

function applyTheme(t: Theme) {
  const el = document.documentElement;
  if (t === "system") delete el.dataset.theme;
  else el.dataset.theme = t;
}
function applyFontSize(s: FontSize) {
  document.documentElement.dataset.fontsize = s;
}

function applyFont(f: Font) {
  document.documentElement.dataset.font = f;
}

export function setFont(f: Font) {
  write(KEYS.font, f);
  applyFont(f);
}
export function setTheme(t: Theme) {
  write(KEYS.theme, t);
  applyTheme(t);
}
export function setFontSize(s: FontSize) {
  write(KEYS.fontSize, s);
  applyFontSize(s);
}

export function applyStoredAppearance() {
  applyTheme(getTheme());
  applyFontSize(getFontSize());
  applyFont(getFont());
}

// Runs as soon as the bundle loads, so the login screen is themed too.
if (typeof document !== "undefined") applyStoredAppearance();
