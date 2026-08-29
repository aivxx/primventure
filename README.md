# Primventure
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

The 3D production world has collapsed into **the Composition**. You are Contestant
#USD-01, an underqualified Primwright recapturing it one authored opinion at a
time.

Primventure is a local, PG-13 OpenUSD dungeon crawl built around the complete
NVIDIA Learn OpenUSD curriculum. Combat is authoring: write Python or USDA,
submit it to real `usd-core` validators, defeat broken layer stacks, and grow a
real USD city in [`world/`](world/). Your persistent city is also your portfolio.

## Enter the Composition

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+, npm,
and Git LFS.

```bash
git lfs install
git lfs pull
uv sync
uv run primventure
```

The command starts the local API and Vite UI, then opens
`http://127.0.0.1:5173`. Submitted Python executes on your machine, so the arena
binds to localhost and should not be exposed as a public service.

## The crawl

- **Floors 0–9** cover orientation, stage authoring, schemas, composition,
  beyond-basics (primvars, kinds, traversal, Hydra), composition arcs, asset
  structure, data exchange, instancing, and certification recap.
- **Rooms and bosses** use `pxr` assertions and original exam-task questions.
  The System takes XP for a missed boss answer; it never wipes a study run.
- **Progression** persists in `game/save.json`: XP, crawler level, domain stats,
  loot, Opinion Points, kiosk upgrades, achievements, and glossary Recipes.
- **The Cookbook** is the original curriculum in [`docs/`](docs/). Quest links
  take you directly to the lesson relevant to the fight.
- **The city** composes from successful submissions under [`world/`](world/).
  Open `world/root.usda` in usdview at any time.

Run only the API with `uv run primventure --api-only`. API documentation is at
`http://127.0.0.1:8000/docs`.

## Build the Cookbook

```bash
uv run sphinx-build -M html docs/ docs/_build/
```

The Cookbook is based on
[NVIDIA Learn OpenUSD](https://docs.nvidia.com/learn-openusd/latest/index.html),
an open-source learning path for the OpenUSD Development Certification. Existing
lesson text, examples, and assets retain their NVIDIA copyright notices and
Apache-2.0/SPDX attribution. Primventure's dungeon, System voice, and progression
are original and do not reproduce characters or plot from other works.

## Develop and test

```bash
uv run pytest game/server/tests
npm --prefix game/web run build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance.
