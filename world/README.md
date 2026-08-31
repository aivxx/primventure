# Primventure World

`root.usda` is the persistent portfolio stage recaptured as the player completes
Floors 0–9. It begins empty; every successful fight adds a stronger authored
layer under `workstreams/`.

This directory is a **template, not a save file**. Nothing the player does is
written here. On startup the server copies this tree into `.primventure/world/`,
which git ignores, and every published layer lands in that copy. Point
`PRIMVENTURE_STATE_DIR` somewhere else to keep play state outside the repository
entirely. Deleting `.primventure/` starts a fresh city from this template.

`assets/` contains small reusable components used by reference, payload, and
instancing quests. Quest runners copy this `world/` tree into the runner's
working directory and provide the writable portfolio path as `STAGE_PATH`.

`districts/` is a reference gallery showing the intended completed topology. It
is not composed into `root.usda`, so it cannot satisfy a room on the player's
behalf. A player's authored stage grows without modifying lesson documentation.
