# Primventure

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](https://www.python.org/)
[![usd-core](https://img.shields.io/badge/usd--core-25.5%2B-76B900.svg)](https://pypi.org/project/usd-core/)

> SYSTEM: The 3D production world *unstitched*. Layers drifted. References went feral. Someone left a `class` where a `def` belonged and the city forgot its own name.
>
> You are Contestant **#USD-01**, an underqualified Primwright. Recapture the Composition one authored opinion at a time.

**Primventure** is a local, PG-13 OpenUSD dungeon crawl. Combat is authoring. You write real Python against [usd-core](https://pypi.org/project/usd-core/), the System grades the stage, and every cleared room publishes into a living city under [`world/`](world/). That city is also your portfolio.

The official [NVIDIA Learn OpenUSD](https://docs.nvidia.com/learn-openusd/latest/index.html) curriculum becomes rooms, bosses, recipes, and a city feed.

---

## The concept

Learn OpenUSD teaches prims, attributes, composition arcs, asset structure, instancing, and data exchange so developers can sit the OpenUSD Development Certification. Primventure takes that same path and makes you *do* it:

1. **Learn this room.** The System introduces the lesson. Neutral beats then cover the concept, the API, the trap, and the recap.
2. **Author it.** The terminal is real `pxr` Python. `STAGE_PATH` and `Save()` are already there. Type under the comments.
3. **Run the room.** usd-core opens your layer and checks the list on the room card. Failures do not wipe the run.
4. **Read the USDA.** Before and after sit on the right. A clear parks you there until you have looked at what you wrote.
5. **Watch the city compose.** City Feed draws `world/root.usda`. Each published room is another opinion on the skyline.

Boss rooms pay **Opinion Points**. Spend them in the Saferoom on Hint Tokens and Opinion X-Rays. The Recipe Tree is your Cookbook index: terms unlock when you have actually authored them.

Submissions use real USD and execute on your machine. The arena binds to localhost on purpose.

---

## Requirements

| What | Why |
| --- | --- |
| **Python 3.12+** | The game and Cookbook both run here. |
| **[uv](https://docs.astral.sh/uv/)** | Installs `usd-core`, FastAPI, Sphinx, and the `primventure` command. |
| **Node.js 20+ and npm** | Vite UI for the dungeon (`game/web`). |
| **Git LFS** | Images, videos, and USD assets in the Cookbook. |
| **A browser** | Chromium-family is what the UI is exercised in. |

Optional: [usdview](https://openusd.org/release/toolset.html#usdview) if you want to open `world/root.usda` outside the feed.

This is not a hosted service. Do not expose the API to the public internet. Submitted Python runs with the privileges of the process that launched it.

---

## Enter the Composition

```bash
git clone https://github.com/NVIDIA-Omniverse/LearnOpenUSD.git primventure
cd primventure

git lfs install
git lfs pull

uv sync
uv run primventure
```

The command starts the FastAPI arena and the Vite UI, then opens **http://127.0.0.1:5173**.

Useful flags:

```bash
uv run primventure --no-browser          # you will walk in yourself
uv run primventure --api-only            # API only, http://127.0.0.1:8000
uv run primventure --port 8000 --web-port 5173
```

API docs live at http://127.0.0.1:8000/docs while the server is up.

Progress is `game/save.json`. The composed city is `world/root.usda` plus whatever you published into `world/workstreams/`. Reset from the UI if you want a clean slate; that wipes workstreams and the preview cache.

### Build the Cookbook (optional)

In-game lessons are enough to crawl. The full Sphinx site is the original curriculum:

```bash
uv run sphinx-build -M html docs/ docs/_build/
uv run python -m http.server 8001 -d docs/_build/html/
```

Then open http://localhost:8001.

### Develop and test

```bash
uv run pytest game/server/tests
npm --prefix game/web run build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [STYLEGUIDE.md](STYLEGUIDE.md) if you are changing lessons or rooms.

---

## The crawl

| Floor | District | What you author |
| --- | --- | --- |
| 0 | Threshold Station | Stages, prims, attributes |
| 1 | Property Ward | Schemas, metadata, time |
| 2 | Blueprint Borough | Scene description blueprints |
| 3 | Composition Quarter | Layers, specifiers, LIVRPS |
| 4 | Beyond the Walls | Primvars, kinds, traversal, Hydra |
| 5 | Arc Foundry | References, payloads, variants, inherits, specializes |
| 6 | Asset Foundry | Model hierarchy and parameterization |
| 7 | Instance Wilds | Scenegraph instances and PointInstancers |
| 8 | Exchange Terminal | Import, extract, transform, validate |
| 9 | Crown District | Certification recap |

Rooms are YAML under [`game/quests/`](game/quests/). Lesson cards live in [`game/lessons/`](game/lessons/), keyed to the Markdown in [`docs/`](docs/). usd-core validates the stage directly.

---

## Where this is sourced from

**Curriculum.** [NVIDIA Learn OpenUSD](https://docs.nvidia.com/learn-openusd/latest/index.html), the open-source learning path for the [OpenUSD Development Certification](https://www.nvidia.com/en-us/learn/certification/openusd-development/). Upstream repository: [NVIDIA-Omniverse/LearnOpenUSD](https://github.com/NVIDIA-Omniverse/LearnOpenUSD).

Lesson text, examples, and assets in `docs/` retain their NVIDIA copyright notices and Apache-2.0 / SPDX attribution. Primventure turns that learning path into a crawl.

**Runtime.** [OpenUSD](https://openusd.org) via `usd-core`. The City Feed reads the composed stage (`Cube`, `Sphere`, `Mesh`, and friends) and draws it in the browser.

**Original to this dungeon.** The System voice, floors, Saferoom, Opinion Points, Recipe Tree, and the persistent city under `world/`. Those do not reproduce characters or plot from other works.

License for this repository: [Apache 2.0](LICENSE).
