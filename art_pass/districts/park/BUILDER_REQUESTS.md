# PARK: builder requests (Claude, cloud, 2026-10-06)

The park needs only **R2: flat ground patches**, which is specified once in `districts/homes/BUILDER_REQUESTS.md`
(exact code + `districts/homes/builder_requests.patch`, which also carries the homes-only R1 / R3).

**Why the park needs it:** the old park is flat. The two lawns (x -50.9..-37 and -33.1..-18.9, z 137.7..156) and the
paved paths had no collision; they were only paint on the ground slab. `PARK_INVENTORY.json` lists them in `ground_patches`
(lawn top 1.2 cm, paving top 1.0 cm), plus a 0.6 m lawn strip beyond the boundary walls (z 164 / x 18) that the
backdrop treeline stands on. Until R2 is merged, the builder ignores `ground_patches`. The park then builds on the plain
ground slab, and the backdrop trees stand on nothing (outside the map, so gameplay is unaffected).

Cost with R2: 4 more merged meshes (26 → 30), no new material.
