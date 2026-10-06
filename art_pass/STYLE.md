# Step 1 — Style sheet (PROPOSED, needs Nizar's ✅)

Revised 2026-10-05 after ChatGPT review T2 (tactile ribs, stone wall, kitchen gear, rooftop antennas).

Source: `neon_crossing/art_direction/approved_neon_tokyo_style.png` (1774×887).
Picture: `art_pass/style_sheet.png`. Exact samples: `art_pass/palette.json` (each with its x,y region).

## Two kinds of colour — don't mix them up

1. **On-screen targets** (style_sheet.png): the final colours in the painting, *after* lighting. We use them to judge our renders.
2. **Texture base colours** (below): what goes into the textures. They are more neutral; the warm dusk lighting makes them look like the painting.
   Painting the warm light *into* textures is the classic mistake: it looks flat and goes wrong in shade.

## Mood

Dusk, the moment the street lights win over the sky. Warm amber at street level, lavender-blue above, small hits of cyan and pink neon.
Lit areas are warm; shadows are cool violet, never black. Clean surfaces, light wear.

## Lighting recipe

| Light | Colour (on screen) | How it's made in game |
|---|---|---|
| Sky | upper #8e8bc5 → horizon #b48cb5 | sky shader + ambient light |
| Sun | low, warm, behind the mall | 1 directional light, shadows on |
| Street lamps / wall lamps | amber, paper lantern #fccc72 | emissive material + baked light |
| Red/orange lanterns | glow #fcd880, shell red | emissive + baked |
| Shop / mall interiors | #c77c38 – #9b7260 | glowing window planes + baked |
| Neon / billboards | cyan #5bd9e4, pink #e763c6 / #f26cc6 | emissive + glow (bloom), small baked spill |

## Materials (texture base colours, sRGB, starting values)

| Material | Base colour | Notes |
|---|---|---|
| Cream plaster | #d8cab4 | smooth, slight streaks, pale edges |
| Warm concrete (terraces, retaining walls) | #b9ab9a | board marks, clean |
| Dark timber (old alley) | #4a3426 | vertical grain, lattice screens |
| Roof tiles (kawara) | #3d3a3e | grey-blue, rounded rows |
| Blue-grey metal (railings, frames, lamps) | #3e4250 | thin, dark, slightly warm in light |
| Stone paving | #a39a92 | large slabs, thin joints |
| Stone wall (retaining walls) | #b3a594 | large jointed blocks, slightly rough faces |
| Darker road asphalt | #4f4d55 | crosswalk stripes off-white #e8e2da |
| Tactile paving | #c69a3c | dot tiles at stops/crossings, raised-rib (line) tiles along walking routes |
| Glass (mall) | tinted #6b7a8c | reflects sky, warm interiors behind |
| Noren curtain | muted red #8a3a36 | soft cloth |
| Foliage | #3c4a24 – #556b2f | ivy, shrubs, pine |
| Sakura | #e7a3c0 | sparse, only accents |

## Props / dressing list (from the painting)

Paper lanterns, red lanterns, noren curtains, menu boards, standing sign, wooden benches and stools, bollards with lamps, tall street lamps, wall lamps, planters with shrubs, potted plants, hanging ivy, pine tree, sakura tree, terrace umbrellas, balcony railings, glass rails, drain grates, vending machine, open-kitchen gear (pots, ladles, prep counter, steamers), rooftop antennas / masts / water tanks, utility box, rubbish bin, billboards (fictional), skyline towers with neon strips.

## Architecture types

- **Old alley (left):** two-storey timber houses, tiled roofs with deep eaves, lattice windows, shop fronts open to the street.
- **Terraces (right):** stacked concrete terraces, balconies with dark rails, warm windows, ivy everywhere.
- **Mall (back):** big curved glass and plaster facade, huge billboard, bridges to the terraces.
- **Skyline:** dark lavender towers with vertical neon strips (cards).
- **Ground:** stone paving, steps between levels, crosswalk, tactile lines.

## Readability rules (it's a shooter)

- Players must stand out: no lighting or neon colour may match the character outlines or the HUD reds.
- Climbable edges (railings, ledges, roof edges) get a consistent lighter trim so parkour routes read.
- Detail density lower than the painting where fights happen; dense dressing at the edges.
