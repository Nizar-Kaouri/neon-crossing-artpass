# Step 0 — Graphics budget (PROPOSED, needs Nizar's ✅)

Development machine = Nizar's laptop: **Intel Arc 130V (integrated GPU), 1600×900**.
This is a mid-range laptop GPU. If the map holds these numbers here, desktop gaming PCs have big headroom.

## Frame targets (whole game, in a real fight: 8 bots + effects + Tempest)

| Preset | Target on the laptop | Frame time |
|---|---|---|
| High | 60 FPS | 16.6 ms |
| Low | 144 FPS (VALORANT top tier) | 6.9 ms |

The map itself may use at most **half** of that (High ≤ 8 ms, Low ≤ 3.5 ms), measured from the worst spot with no players.
The other half is characters, effects, HUD and game code.

For reference: the old lab rebuild measured 4–12 ms with up to ~4 000 draw calls, with no players at all. That is over budget.

## Per-view limits (worst camera position on the map)

| What | High | Low |
|---|---|---|
| Draw calls | ≤ 1 500 | ≤ 800 |
| Visible triangles | ≤ 3 M | ≤ 1 M |
| Shadow-casting lights | 1 (the dusk sun) | 1, shorter shadow distance |
| Real-time lights (no shadow) visible at once | ≤ 16 | ≤ 4 |
| Screen effects | glow, SSAO, depth fog | glow only, depth fog |
| Never | SSR, SDFGI, volumetric fog, real-time shadows on lanterns | |

## Whole-map limits

| What | Limit |
|---|---|
| Unique materials | ≤ 40 |
| Texture memory (VRAM) | ≤ 1 GB High, ≤ 512 MB Low |
| Texture size | 2048² for trim sheets and atlases, 1024² for props, nothing larger |
| Texture format | VRAM-compressed (BC7 / ASTC), with mipmaps |
| Building kit piece | ≤ 2 000 triangles |
| Prop | ≤ 5 000 triangles (hero prop ≤ 15 000 with a LOD) |
| Load time | ≤ 15 s on the laptop |

## How the look stays inside this budget

- **Lighting is baked** (LightmapGI). Lanterns, windows and neon are glowing materials plus baked light, not real lamps. This is where most of the artwork's mood comes from, and it costs almost nothing at runtime.
- **Trim sheets**: a few shared textures for the whole building kit, so few materials and few draw calls.
- **Instancing (MultiMesh)** for repeated props and plants.
- **LODs, visibility ranges and occluders**: far things get simpler or vanish, buildings hide what's behind them.
- **Skyline = painted cards**, not 3D towers.

## How we measure

F9 overlay in the slice / map scene: frame time, RENDERING ms, draw calls. Nizar runs it on the laptop at the worst spots and sends a screenshot.

## Preset definitions (2026-10-06, used for every gate measurement)

Viewer: press **L** (Low) or **H** (High), or start with `-- --preset=low|high`. Map only, 1600×900 3D resolution, V-Sync off, after a valid bake.

| Setting | High | Low |
|---|---|---|
| SSAO | on | off |
| Glow, depth fog | on | on |
| Live lamp lights | off (baked) | off (baked) |
| Anti-aliasing | MSAA 2× | FXAA (no MSAA) |
| Sun shadow distance / splits | 80 m / 4 | 40 m / 2 |
| Shadow atlas | 4096 | 2048 |
