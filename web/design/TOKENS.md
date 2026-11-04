# Haru design tokens

Single source: `web/src/styles/tokens.css` (values) + `web/src/styles/theme.css` (Tailwind names).
Rule: a screen never writes a raw color, font, radius or shadow. It uses the token names below or the components in `web/src/components/ui/`.
Check it by eye at `/haru/?demo=ui` (no login, no server): theme, font and size switches are on top.

## Colors (light / dark switch by system setting or Settings -> theme)
| Tailwind | CSS variable | Use |
|---|---|---|
| bg-bg | --haru-bg | page background |
| bg-surface | --haru-surface | inputs, cards, sidebar |
| bg-surface-2 | --haru-surface-2 | hover, selected, tab track |
| border-line | --haru-border | all borders |
| text-fg / text-fg-2 | --haru-fg / --haru-fg-2 | main / secondary text |
| text-muted | --haru-muted | hints, captions |
| bg-accent, hover:bg-accent-hover, text-accent-strong | --haru-accent (#DA7756) | the one main action, focus border, selected |
| text-accent-fg | --haru-accent-fg | text on accent |
| bg-bubble | --haru-user-bubble | my message bubble |
| text-danger / bg-danger | --haru-danger | delete, errors |

## Fonts (Settings -> 글꼴: 기본 / 고딕 / 시스템 via `data-font` on <html>)
| Tailwind | Variable | Stack |
|---|---|---|
| font-sans (default on body) | --haru-font-ui | Pretendard Variable |
| font-reading (answers) | --haru-font-reading | Source Serif 4 (Latin/digits) + MaruBuri (Hangul); 고딕 = Pretendard; 시스템 = system |
| font-mono (code) | --haru-font-mono | JetBrains Mono |
Answer text size/leading: --haru-reading-size 1.0625rem, --haru-reading-leading 1.8. Whole-UI size: `data-fontsize` small 14px / medium 16px / large 18px on <html> (rem based).
Weights bundled: Pretendard variable (split by unicode-range), Source Serif 4 400/700, MaruBuri 400/700, JetBrains Mono 400. Licenses: `web/public/licenses/FONTS.md`.

## Shape and space
| Tailwind | Variable | Value | Use |
|---|---|---|---|
| rounded-control | --haru-radius-control | 0.75rem | buttons, inputs, menu items, tabs |
| rounded-card | --haru-radius-card | 1rem | cards, dialogs, menus, composer |
| rounded-bubble | --haru-radius-bubble | 1.25rem | my message bubble |
| rounded-pill | --haru-radius-pill | full | chips |
| shadow-pop | --haru-shadow-pop | soft | menus and dialogs only |
Control height: 2.75rem (44px) is built into Button, IconButton, Input, Chip, MenuItem. Spacing uses the Tailwind 4px scale (p-2, gap-3, px-4); page content max width max-w-3xl, forms max-w-2xl.

## Components (`web/src/components/ui/`)
Button (primary / secondary / ghost / danger), IconButton (label required), Input, Textarea, Card, UserBubble, Reply, Tabs, Dialog (full screen on phone), cx().
- Chip: filter chip, or dropdown chip with `caret` (+ `icon`), e.g. 환경 ▾ / 저장소 ▾ / 모델 ▾ / 권한 모드 ▾ (Code input row).
- Menu / MenuItem / MenuDivider / SubMenu: MenuItem takes `check` (✓), `toggle` (on/off switch), `shortcut` (e.g. "1"), `hint` (second line), `icon`, `submenu` (›). SubMenu opens to the side on desktop and indented below on phone.
The example is in the check screen section "칩 · 하위 메뉴 예시".

## Migration status
Stage 1, part 1: tokens, components and the check screen exist. Existing screens still use their own classes; part 2 moves them to these components and removes the global 44px rule in `mobile.css`.
