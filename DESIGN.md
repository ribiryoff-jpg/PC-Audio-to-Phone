# Design

Cursor-like minimal tool UI. Monochrome system in both themes; green/red are
functional status only, never decoration.

## Color

Dark (default): bg `#0a0a0a`, surface `#141414`, raised `#1c1c1c`,
border `#262626`, text `#e5e5e5`, muted `#a1a1a1`.
Light: bg `#ffffff`, surface `#f5f5f5`, raised `#ececec`,
border `#e2e2e2`, text `#0a0a0a`, muted `#525252`.
Status only: ok `#22c55e`, err `#ef4444`.

## Typography

System stack only (`Segoe UI`, Tahoma, Arial on Windows; system-ui on web).
One family, weight contrast (400/700). PIN/URL/code in monospace
(Consolas / ui-monospace). Body ≤ 65ch. `text-wrap: balance` on headings.

## Shape & Spacing

Radius: cards 12px, controls 8px, pills for segmented toggles.
Hairline 1px borders, no shadows (or a single subtle one, never border+shadow
together). Rhythm: 8px base scale (8/12/16/24).

## Components

- Segmented control: theme (dark/light) and language (AR/EN/FR/ES).
- Mode cards: Instant vs WebRTC vs Background, each with name + delay + one-line note.
- Steps: one real numbered sequence (1 Wi-Fi, 2 pair buds, 3 code + play).
- Status row: icon glyph (● ○ ✓ !) + text; never color alone.
- Big Play/Stop buttons (phone ≥56px tall); desktop Start/Stop + Copy link.
- QR stays pure black-on-white in both themes.

## Layout

Phone: single 420px column, header → steps → mode → code → transport →
volume → status → tips. Desktop: same order stacked in a 420px window.
No nav, no tabs, no nested cards.
