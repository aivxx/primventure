import { useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  ArrowRight, Backpack, Boxes, BookOpen, Building2, CheckCircle2, ChevronLeft,
  ChevronRight, Circle, CircleDollarSign, Clapperboard, Code2, FlaskConical, ListTree,
  Gem, HelpCircle, Lightbulb, ListChecks, LockKeyhole, Play, RefreshCw, Shield,
  ShoppingCart, Skull, Sparkles, Swords, TerminalSquare, Trash2, Trophy, Tv, X,
  XCircle, Zap,
} from "lucide-react";
import * as THREE from "three";

type Language = "python" | "usda" | "none";
type Question = { prompt: string; choices?: string[]; answer?: number; answer_key?: string };
type LessonBeat = {
  kind: "concept" | "api" | "pitfall" | "recap";
  heading: string; system?: string; body?: string; points?: string[]; code?: string;
};
type Lesson = {
  source: string; title: string; objective: string; intro: string;
  beats: LessonBeat[]; apply: string;
};
type Quest = {
  id: string; title: string; floor: number; floor_name: string; neighborhood: string;
  kind: "orientation" | "room" | "neighborhood_boss" | "city_boss" | "floor_boss";
  brief: string; language: Language; starter: string; xp: number; reward?: string | object;
  cookbook: string; unlocked: boolean; completed: boolean; exam_tasks: string[];
  stats: Record<string, number>; questions?: Question[]; lesson?: Lesson | null;
  opinion_points: number; expects: string[]; submission: string;
  home_floor?: boolean; boss_fee?: number; boss_fee_kind?: string;
  free_hint?: boolean; free_census?: boolean;
  census_armed?: boolean; census_paid?: boolean;
};
type ShopItem = {
  name: string; description: string; cost: number; repeatable?: boolean;
  kind?: "consumable" | "upgrade";
};
type ClassPath = {
  id: string; title: string; blurb: string; kit: string; perks: string[];
};
type ClassBenefits = {
  catalog: ClassPath[];
  home_floors: number[];
  home_names: string[];
  recipe_drip_op: number;
  recipe_drip_cap: number;
  claims: Record<string, boolean>;
};
type CurioOffer = { name: string; trophy_cost: number; inventory: Record<string, number> };
type CurioDesk = { unstamped: number; held: number; offers: Record<string, CurioOffer> };
type PlayerState = {
  contestant: string; title: string; level: number; xp: number; next_level_xp: number;
  opinion_points: number; completed_quests: string[]; stats: Record<string, number>;
  inventory: Record<string, number>; upgrades: string[]; recipes: string[];
  achievements: string[]; specialization?: string; shop: Record<string, ShopItem>;
  class_benefits?: ClassBenefits; stamped_items?: Record<string, number>; curio?: CurioDesk;
};
type CurioResponse = { stamped: Record<string, number>; granted: Record<string, number>; state: PlayerState };
type Recipe = { id: string; label: string; category: string; unlocked: boolean; affinity?: boolean };
type RunResult = {
  success: boolean; output: string; system_message: string;
  results: Array<{ rule: string; passed: boolean; message: string }>; state: PlayerState;
  before_usda: string; after_usda: string;
};
type USDAView = { before_usda: string; after_usda: string };
type Toast = { kind: "success" | "error" | "info"; title: string; message: string };
type CensusNode = {
  path: string; specifier: string; type_name: string; kind: string;
  properties: string[]; extra_properties: number; flags: string[];
};
type CheckObservation = { rule: string; target: string; observed: string };
type Census = {
  stage: {
    default_prim?: string; up_axis?: string; meters_per_unit?: number;
    sublayers?: string[]; time_range?: number[];
  };
  prims: CensusNode[];
  observations: CheckObservation[];
  truncated: boolean;
};
type AssistResult = {
  kind: "hint" | "census";
  title: string;
  message?: string;
  census?: Census;
};
type HintResponse = { hint: string; state: PlayerState };
type CensusResponse = { census: Census; state: PlayerState };

const CLASS_PATHS: ClassPath[] = [
  {
    id: "Compositor",
    title: "Compositor",
    blurb: "Layers, composition arcs, and competing opinions resolving into one stage.",
    kit: "Declare and receive 1 Prim Census.",
    perks: [
      "Home: Opinion Quarter and Composition Highlands.",
      "Census restocks cost 1 OP.",
      "City bosses +1 OP, floor bosses +2 OP on home floors.",
      "Home-floor boss misses charge half XP.",
      "One free census after a fail per home floor, even at zero stock.",
      "Affinity recipes pay +1 OP, up to 5 for the crawl.",
    ],
  },
  {
    id: "Aggregator",
    title: "Aggregator",
    blurb: "Scalable assets: payloads, kinds, instancing, and inspectable workstreams.",
    kit: "Declare and receive 1 Hint Token.",
    perks: [
      "Home: Hierarchy Foundry and Prototype Wilds.",
      "Hint restocks grant 3 tokens instead of 2.",
      "City bosses +1 OP, floor bosses +2 OP on home floors.",
      "Home-floor boss misses charge half XP.",
      "One free Hint per home floor, even at zero stock.",
      "Affinity recipes pay +1 OP, up to 5 for the crawl.",
    ],
  },
  {
    id: "Exchanger",
    title: "Exchanger",
    blurb: "Moving data between OpenUSD and other tools with honest units and validation.",
    kit: "Declare and receive 1 Hint Token and 1 Prim Census.",
    perks: [
      "Home: Customs Terminal.",
      "Hint and census restocks both cost 1 OP.",
      "Neighborhood bosses +1 OP, city bosses +2 OP on Customs Terminal.",
      "Home-floor boss misses charge half XP.",
      "The first Customs Terminal boss miss costs 0 XP.",
      "Affinity recipes pay +1 OP, up to 5 for the crawl.",
    ],
  },
];

const RESET_OPTIONS = [
  {
    scope: "city",
    title: "Demolish the City",
    blurb: "Deletes every layer you published and empties world/root.usda. Your record, level, and Opinion Points survive.",
    confirm: "The skyline goes. Cleared rooms stay cleared, so any episode can be rerun to rebuild its block.",
    action: "DEMOLISH",
  },
  {
    scope: "all",
    title: "Wipe the Whole Crawl",
    blurb: "Demolishes the city and clears the save. Back to Floor 00, level 1, nothing banked.",
    confirm: "Everything goes: skyline, level, XP, Opinion Points, items, and every cleared room.",
    action: "WIPE IT ALL",
  },
] as const satisfies readonly { scope: ResetScope; title: string; blurb: string; confirm: string; action: string }[];

const ONBOARDED_KEY = "primventure.onboarded.v2";
const GUIDED_KEY = "primventure.guided";
const LESSONS_READ_KEY = "primventure.lessons-read.v1";
const USDA_REVIEW_KEY = "primventure.usda-review";
const VIEW_KEY = "primventure.view.v1";

type Tab = "map" | "skills" | "kiosk";
// "city" tears down what was published and leaves the record standing; "all"
// takes the save with it.
type ResetScope = "city" | "all";
type GuideTarget = "lesson" | "editor" | "run" | "usda" | "map" | "level" | "payout" | "consumables" | "keyitems" | "class" | "saferoom" | "recipes" | "feed";
// Panels on the left edge have no room for an arrow beside them, and the
// tutorial card owns the bottom left, so those targets get pointed at from the
// right instead of being covered by their own callout. Targets in the header
// strip have nothing beside them either, so they get pointed at from below.
type PointerSide = "left" | "right" | "up";
const POINTER_SIDE: Record<GuideTarget, PointerSide> = {
  lesson: "right",
  editor: "right",
  run: "left",
  usda: "right",
  map: "right",
  level: "up",
  payout: "left",
  consumables: "left",
  keyitems: "left",
  class: "right",
  saferoom: "right",
  recipes: "right",
  feed: "left",
};
const GUIDE_STEPS: Array<{ target: GuideTarget; title: string; body: string }> = [
  {
    target: "lesson",
    title: "Learn this room",
    body: "The System introduces the official lesson, then hands you the concepts, API calls, and traps this room needs. Open it whenever you want — you can run the room without reading it first.",
  },
  {
    target: "editor",
    title: "Write the code",
    body: "This is the terminal. It holds real Python, with a blank line under each instruction to write on. STAGE_PATH and the closing Save() are already supplied.",
  },
  {
    target: "run",
    title: "Run the room",
    body: "usd-core opens your stage and checks it against the list in the room card. Ordinary rooms cost nothing to retry. Boss rooms ask you to confirm first, because a wrong answer costs XP.",
  },
  {
    target: "usda",
    title: "Read the USDA you authored",
    body: "This panel holds the layer itself. BEFORE is the stage the room handed you, AFTER is what your code wrote, and the first changed line is highlighted.",
  },
  {
    target: "map",
    title: "Move through the floors",
    body: "Clear the rooms to learn the floor. The boss is the exit exam, and your cleared work stacks up as a real USD city in world/. Cleared floors become playback episodes. The audience rewatches those reruns while you stay on the live broadcast.",
  },
  {
    target: "level",
    title: "Find your level here",
    body: "Your current level is always in the LVL badge at the top right. Clearing a room pays its XP once, and every 100 XP raises that number. Prerequisites are not the only lock: some rooms also require a level. Losing to a boss costs XP but never lowers your level.",
  },
  {
    target: "payout",
    title: "Get paid in Opinion Points",
    body: "Opinion Points are the only currency, and boss rooms are what pay them. This counter holds your balance and names the next room that will top it up.",
  },
  {
    target: "consumables",
    title: "Spend it on consumables",
    body: "Hint Tokens buy you a clue for the room you are stuck on, even before a run. A Prim Census works only after a failed run: it lists the prims USD actually composed — paths, specifiers, types, kinds — and the real value behind each failing check, so you can see that you authored /City/NamePlate or that cityName is still unset. The checklist tells you the target; the census tells you your stage. Click one here to use it, and hit SAFEROOM to buy more once a boss has paid you.",
  },
  {
    target: "keyitems",
    title: "Key Items are your transcript",
    body: "Clearing an ordinary room leaves a souvenir here: a Copper Scene Key for your first prim, an Offset Wrench for layer offsets. Each one names an OpenUSD concept you authored. The Saferoom's Curio Desk trades three of them for Hint Tokens or four for Prim Censuses, and it stamps a trophy rather than taking it, so cashing one in never erases the record.",
  },
  {
    target: "class",
    title: "Declare a class at level 2",
    body: "At level 2, declare a class in the Saferoom. Each path grants a starter kit, cheaper restocks, extra Opinion Points on its home floors, and a softer boss fee. Classes never skip rooms or hand you the answer. A full crawl reset is the only way to choose again.",
  },
  {
    target: "saferoom",
    title: "Restock in the Saferoom",
    body: "This is where Opinion Points turn into supplies: more Hint Tokens and Prim Censuses, plus permanent upgrades. Further down, the Curio Desk sells the same consumables for Key Items instead of points. Nothing sold here clears a room for you.",
  },
  {
    target: "recipes",
    title: "Collect the recipes",
    body: "The Recipe Tree is your Cookbook index. Every room names the OpenUSD terms it uses, and clearing it unlocks those nodes, so the tree is a record of what you have actually authored.",
  },
  {
    target: "feed",
    title: "Watch the city compose",
    body: "City Feed renders world/root.usda, the stage every cleared room publishes into. It redraws after each win, so the skyline is the running total of everything you have authored.",
  },
];

const emptyState: PlayerState = {
  contestant: "USD-01", title: "Unlicensed Primwright", level: 1, xp: 0,
  next_level_xp: 100, opinion_points: 0, completed_quests: [],
  stats: { Authoring: 0, Composition: 0, Aggregation: 0, Debug: 0, Pipeline: 0 },
  inventory: {}, upgrades: [], recipes: [], achievements: [], shop: {},
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function questStatus(quest: Quest): "locked" | "available" | "complete" | "boss" {
  if (quest.completed) return "complete";
  if (!quest.unlocked) return "locked";
  return quest.kind.endsWith("boss") ? "boss" : "available";
}

function floorStatus(rooms: Quest[]): "locked" | "live" | "cleared" {
  if (rooms.some((quest) => quest.unlocked && !quest.completed)) return "live";
  if (rooms.length > 0 && rooms.every((quest) => quest.completed)) return "cleared";
  return "locked";
}

function episodeCode(floor: number) {
  return `S01E${String(floor).padStart(2, "0")}`;
}

function episodeTag(kind: "locked" | "live" | "cleared") {
  if (kind === "live") return "ON AIR";
  if (kind === "cleared") return "RERUN";
  return "UNAIRED";
}

function firstChangedLine(before: string, after: string): number {
  const original = before.split("\n");
  const modified = after.split("\n");
  const length = Math.max(original.length, modified.length);
  for (let index = 0; index < length; index += 1) {
    if (original[index] !== modified[index]) return index + 1;
  }
  return 1;
}

function cookbookUrl(path: string) {
  const relative = path.replace(/^docs\//, "").replace(/\.md$/, ".html");
  return `/cookbook/${relative}`;
}

// The host talks; the lesson teaches. Every line the System speaks gets the
// same nameplate so beats never read as unattributed narration.
function SystemLine({ text, tone }: { text: string; tone: "intro" | "aside" | "apply" }) {
  return <div className={`system-line ${tone}`}>
    <span className="system-avatar">SYS</span>
    <div>
      <span className="system-tag">THE SYSTEM</span>
      <p>{text}</p>
    </div>
  </div>;
}

function lessonsRead(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(LESSONS_READ_KEY) || "[]") as string[]);
  } catch {
    return new Set();
  }
}

/** Where the player was looking last, so a reload does not relocate them. */
type StoredView = { landing: boolean; tab: Tab; questId: string | null; floor: number | null; scope: "floor" | "all" };

function storedView(): Partial<StoredView> {
  try {
    return JSON.parse(localStorage.getItem(VIEW_KEY) || "{}") as Partial<StoredView>;
  } catch {
    return {};
  }
}

/** Merges rather than replaces, so a field that is not resolved yet keeps its stored value. */
function rememberView(patch: Partial<StoredView>) {
  localStorage.setItem(VIEW_KEY, JSON.stringify({ ...storedView(), ...patch }));
}

const TICKER = [
  "A NEW CONTESTANT HAS ENTERED THE COMPOSITION",
  "THE BROADCAST IS LIVE IN EVERY REMAINING TIMEZONE",
  "NO EXPERIENCE REQUIRED · NONE DETECTED EITHER",
  "TEN FLOORS · ONE OPENS AT A TIME · THE REST STAY SEALED",
  "THE PREVIOUS CONTESTANT DECLINED TO READ THE BRIEF",
  "SPONSORS RECOMMEND A STRATEGY · PANIC FAILED FOCUS TESTING",
  "NOTHING HERE IS PERMANENT EXCEPT THE CITY YOU BUILD",
];

const SPONSORS = [
  "THIS SEGMENT IS BROUGHT TO YOU BY THE ESTATE OF THE FOURTH FLOOR",
  "SPONSOR: A FIRM THAT NO LONGER RESOLVES · TERMS UNAVAILABLE",
  "VIEWER DISCRETION IS ADVISED · THE SYSTEM DECLINED",
  "STANDINGS UPDATE HOURLY · YOUR NAME REMAINS CONSPICUOUSLY ABSENT",
];

function BroadcastChrome() {
  const [now, setNow] = useState(() => Date.now());
  const [viewers, setViewers] = useState(4_412_908);
  const start = useRef(Date.now());

  useEffect(() => {
    const clock = window.setInterval(() => setNow(Date.now()), 100);
    const audience = window.setInterval(
      () => setViewers((count) => Math.max(1_000_000, count + Math.floor(Math.random() * 900) - 260)),
      1800,
    );
    return () => { window.clearInterval(clock); window.clearInterval(audience); };
  }, []);

  const elapsed = now - start.current;
  const pad = (value: number) => String(value).padStart(2, "0");
  const timecode = [
    pad(Math.floor(elapsed / 3_600_000)),
    pad(Math.floor(elapsed / 60_000) % 60),
    pad(Math.floor(elapsed / 1000) % 60),
    pad(Math.floor(((elapsed % 1000) / 1000) * 24)),
  ].join(":");

  return <div className="broadcast-chrome" aria-hidden="true">
    <div className="chrome-bug"><b>SYS</b><span>1</span></div>
    <div className="chrome-tc"><i className="rec-dot" />REC<em>{timecode}</em></div>
    <div className="chrome-cam">CAM 04 · INTAKE FOYER · SIGNAL <b>98%</b></div>
    <span className="chrome-corner tl" /><span className="chrome-corner tr" />
    <span className="chrome-corner bl" /><span className="chrome-corner br" />
    <div className="chrome-roll" />
    <div className="broadcast-bottom">
      <span className="bottom-viewers"><i /> {viewers.toLocaleString()} WATCHING</span>
      <div className="ticker-window">
        <div className="ticker-track slow">
          {[...SPONSORS, ...SPONSORS].map((line, index) => <em key={index}>{line}</em>)}
        </div>
      </div>
      <span className="bottom-meter"><i /><i /><i /><i /><i /></span>
    </div>
  </div>;
}

function Landing({ onStart, hasProgress, nextQuest, quests, floors }: {
  onStart: () => void; hasProgress: boolean; nextQuest: Quest | null;
  quests: Quest[]; floors: Array<[number, Quest[]]>;
}) {
  const bossCount = quests.filter((quest) => quest.kind.endsWith("boss")).length;
  // The tower and the billing reflect the run in progress, so a returning
  // contestant is not told they are still waiting on the opening floor.
  const liveFloor = nextQuest?.floor ?? 0;
  const floorLabel = String(liveFloor).padStart(2, "0");
  return <div className="landing">
    <BroadcastChrome />
    <div className="landing-ticker">
      <span className="ticker-live"><span className="live-dot" /> LIVE</span>
      <div className="ticker-window">
        <div className="ticker-track">
          {[...TICKER, ...TICKER].map((line, index) => <em key={index}>SYSTEM // {line}</em>)}
        </div>
      </div>
      <span className="ticker-clock">SEASON 01 · EP {floorLabel}</span>
    </div>
    <div className="landing-inner">
      <header className="landing-hero">
        <div className="landing-mark"><span>P</span></div>
        <span className="landing-eyebrow">SEASON 01 · LIVE, UNRENDERED, AND MILDLY EMBARRASSED</span>
        <h1 data-text="PRIMVENTURE">PRIMVENTURE</h1>
        <p className="landing-tagline">
          “Other dungeons hand you a sword. I hand you a keyboard, ten floors of architecture that no longer agrees
          with itself, and my full attention.”
        </p>
        <span className="tagline-by">— YOUR HOST, THE SYSTEM</span>
        <p className="landing-context">
          The subject is <b>OpenUSD</b> — the open standard for describing 3D scenes across film, games, and simulation.
          The lessons are NVIDIA's Learn OpenUSD curriculum. The judge is <b>usd-core</b>, the real library, which has
          never once been impressed.
        </p>
      </header>

      <div className="lower-third">
        <span className="lt-accent" />
        <div className="lt-body">
          <strong>CONTESTANT #USD-01</strong>
          <span>PRIMWRIGHT · UNDERQUALIFIED · {hasProgress ? `LIVE ON FLOOR ${floorLabel}` : "AWAITING FLOOR 00"}</span>
        </div>
        <span className="lt-live"><i className="live-dot" /> ON AIR</span>
      </div>

      <section className="landing-transmission">
        <div className="transmission-tag">SYSTEM BROADCAST · ORIENTATION · YOU CANNOT SKIP THIS</div>
        <p>
          Welcome, Contestant. Congratulations on the courage it took to press a button. Something broke the world
          where 3D gets made — film, games, simulation, all of it. Was it me? That is under review. What is left is a
          city that no longer makes sense. Rooms disagree with each other. Buildings have forgotten their own shape.
          Two floors are in litigation over which one is the fourth floor. I have taken no sides, publicly.
        </p>
        <p>
          The city is called <b>the Composition</b>. I have sealed it into ten floors, for your safety and my ratings.
          Every room holds exactly one thing that no longer works. Repair the thing and the room lets you leave. Finish
          a floor and I release whatever has been pacing at the top of it, because a season needs structure. No, I will
          not tell you what it is. Half the fun is yours. The other half is mine, and mine is bigger.
        </p>
        <p>
          You have been <b>filed as a Primwright</b> — my term for someone who writes the instructions that tell a 3D
          scene what it is. Save the gratitude. Your interview consisted of me skimming one line of your work history,
          laughing, and printing a badge. It reads <em>Contestant #USD-01</em>. <em>Primwright</em>.
          <em> Underqualified</em>. I ran out of room before I ran out of adjectives.
        </p>
        <p>
          House rules, which you will ignore in roughly four minutes. I assign the work. Real tooling grades it.
          Every failure therefore reaches an impartial third party and me, personally, out loud.
          Nothing you build is ever taken from you. Legal insisted. Everything you get right, the city keeps forever,
          which I am told is called a portfolio and which I am told humans enjoy. Begin whenever you are ready. The
          audience is already seated. They were promised a spectacle, and so far they have you.
          <span className="caret" />
        </p>
        <div className="transmission-sign">— THE SYSTEM · HOST, JUDGE, AND NOT YOUR FRIEND</div>
      </section>

      <section className="landing-cast">
        <div><span>THE COMPOSITION</span><p>The collapsed city. Ten floors. Reclaimed one honest fix at a time.</p></div>
        <div><span>THE SYSTEM</span><p>Host, judge, building inspector. Enjoys the rooms you lose.</p></div>
        <div><span>A PRIMWRIGHT</span><p>Your new title. You write what a 3D scene is. Skill optional at intake.</p></div>
      </section>

      <div className="landing-stats">
        <div><b>{quests.length || "—"}</b><small>ROOMS TO FIX</small></div>
        <div><b>{bossCount || "—"}</b><small>THINGS IN THE WAY</small></div>
        <div><b>10</b><small>SEALED FLOORS</small></div>
        <div><b>01</b><small>CITY TO REBUILD</small></div>
      </div>

      <section className="landing-how">
        <h2>COMBAT, SUCH AS IT IS</h2>
        <ol className="landing-steps">
          <li><b>01</b><strong>Read the room</strong><span>Two lines of job from the System, plus the lesson it was stolen from.</span></li>
          <li><b>02</b><strong>State your case</strong><span>Finish the starter code in the room's terminal. It is ordinary Python.</span></li>
          <li><b>03</b><strong>Face the judges</strong><span>OpenUSD opens what you wrote and rules on it, line by line.</span></li>
        </ol>
        <p className="landing-note">
          Win and your work is filed into a real 3D city that keeps growing on your disk, and the room pays XP once —
          every 100 of it is a level, and a few rooms will not open below one. Miss and the System says something
          unkind and hands the room straight back. Nothing you build is ever taken away; losing to a boss costs a
          little XP and never a level.
        </p>
      </section>

      <section className="landing-tower">
        <h2>THE TOWER · TEN FLOORS, NO ELEVATOR</h2>
        <p className="landing-note">
          Cleared in order. Every floor teaches a new part of OpenUSD and ends with something that declines to let you
          pass politely. The System keeps that final inconvenience classified for comedic purposes.
        </p>
        <div className="tower-grid">
          {floors.map(([floor, rooms]) => {
            const bosses = rooms.filter((room) => room.kind.endsWith("boss")).length;
            const cleared = floorStatus(rooms) === "cleared";
            const live = !cleared && floor === liveFloor;
            const done = rooms.filter((room) => room.completed).length;
            return <div className={`tower-floor ${live ? "open" : ""} ${cleared ? "cleared" : ""}`} key={floor}>
              <span className="tower-index">{String(floor).padStart(2, "0")}</span>
              <div>
                <strong>{rooms[0]?.floor_name}</strong>
                <small>
                  {live && done > 0
                    ? `${done} of ${rooms.length} rooms · ${bosses} guarded`
                    : `${rooms.length} rooms · ${bosses} guarded`}
                </small>
              </div>
              {cleared
                ? <em className="tower-open cleared">CLEARED</em>
                : live
                  ? <em className="tower-open">OPEN</em>
                  : <LockKeyhole size={13} />}
            </div>;
          })}
        </div>
      </section>

      <div className="landing-launch">
        <button className="landing-cta" onClick={onStart} autoFocus>
          {hasProgress ? "CONTINUE RUN" : "ENTER THE COMPOSITION"} <ArrowRight size={18} />
        </button>
        <p className="landing-next">
          {quests.length === 0
            ? "Connecting to the local arena…"
            : nextQuest
              ? <>Floor {floorLabel} · {hasProgress ? "next assignment" : "your first assignment"}: <b>{nextQuest.title}</b></>
              : "Every room cleared. The season is in the can."}
        </p>
        <small className="landing-fine">
          No OpenUSD experience required. This RPG-style game is based on NVIDIA's open-source{" "}
          <a href="https://docs.nvidia.com/learn-openusd/latest/index.html" target="_blank" rel="noreferrer">Learn OpenUSD</a>{" "}
          learning path and is meant as a study companion for the{" "}
          <a href="https://www.nvidia.com/en-us/learn/certification/openusd-development/" target="_blank" rel="noreferrer">OpenUSD Development Certification</a>.
          Primventure is not an official NVIDIA product. Designed and created by Ashley Malqui.
          Contributions are welcome — questions, ideas, and pull requests to{" "}
          <a href="mailto:ashmalqui@gmail.com">ashmalqui@gmail.com</a>.
        </small>
      </div>
    </div>
  </div>;
}

function GuideDock({ step, onBack, onNext, onClose }: {
  step: number; onBack: () => void; onNext: () => void; onClose: () => void;
}) {
  const current = GUIDE_STEPS[step];
  const last = step === GUIDE_STEPS.length - 1;
  return <div className="guide-dock">
    <div className="guide-head">
      <span>HOW TO PLAY · {step + 1}/{GUIDE_STEPS.length}</span>
      <button onClick={onClose} aria-label="Close tutorial"><X size={15} /></button>
    </div>
    <strong>{current.title}</strong>
    <p>{current.body}</p>
    <div className="guide-actions">
      <button className="ghost" onClick={onBack} disabled={step === 0}>BACK</button>
      <button className="solid" onClick={last ? onClose : onNext}>
        {last ? "START PLAYING" : "NEXT"} <ArrowRight size={14} />
      </button>
    </div>
  </div>;
}

type ScenePrim = {
  path: string; name: string; type: string; matrix: number[];
  role: "geometry" | "light" | "pad";
  color?: [number, number, number];
  size?: number; radius?: number; height?: number; axis?: string;
  points?: number[][]; triangles?: number[]; intensity?: number;
};
type WorldScene = { up_axis: string; meters_per_unit: number; prims: ScenePrim[] };

/** The district a prim belongs to, so the plan view can give it a plot. */
function districtOf(path: string) {
  const parts = path.split("/").filter(Boolean);
  return parts.length > 1 ? parts.slice(0, 2).join("/") : parts[0] || "City";
}

/** Plot centres on a square grid, ordered so the city grows outward evenly. */
function planGrid(count: number, pitch: number) {
  const columns = Math.max(1, Math.ceil(Math.sqrt(count)));
  const rows = Math.ceil(count / columns);
  return Array.from({ length: count }, (_, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    return new THREE.Vector3(
      (column - (columns - 1) / 2) * pitch,
      0,
      (row - (rows - 1) / 2) * pitch,
    );
  });
}

/** One gprim, as three.js geometry. Implicit shapes carry parameters, not points. */
function primGeometry(prim: ScenePrim): THREE.BufferGeometry | null {
  if (prim.type === "Cube") {
    const size = prim.size ?? 2;
    return new THREE.BoxGeometry(size, size, size);
  }
  if (prim.type === "Sphere") return new THREE.SphereGeometry(prim.radius ?? 1, 24, 16);
  if (prim.type === "Cylinder" || prim.type === "Capsule") {
    return new THREE.CylinderGeometry(prim.radius ?? 1, prim.radius ?? 1, prim.height ?? 2, 20);
  }
  if (prim.type === "Cone") return new THREE.ConeGeometry(prim.radius ?? 1, prim.height ?? 2, 20);
  if (prim.type === "Mesh" && prim.points?.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(prim.points.flat(), 3));
    if (prim.triangles?.length) geometry.setIndex(prim.triangles);
    geometry.computeVertexNormals();
    return geometry;
  }
  return null;
}

/** Lights and addressed-but-empty prims, drawn as landmarks rather than buildings. */
function landmarkObject(prim: ScenePrim): THREE.Object3D | null {
  if (prim.role === "light") {
    const color = new THREE.Color().setRGB(...(prim.color ?? [1, 0.8, 0.18]));
    const radius = Math.max(prim.radius ?? 0.5, 0.35);
    const beacon = new THREE.Group();
    beacon.add(new THREE.Mesh(
      new THREE.SphereGeometry(radius, 18, 12),
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 1.6 }),
    ));
    beacon.add(new THREE.Mesh(
      new THREE.SphereGeometry(radius * 1.7, 14, 10),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.12 }),
    ));
    // A real light on the stage, so the feed is lit by what the player authored.
    beacon.add(new THREE.PointLight(color, Math.min((prim.intensity ?? 1) / 250, 6), 0, 2));
    return beacon;
  }
  if (prim.role === "pad") {
    const color = new THREE.Color().setRGB(...(prim.color ?? [0.42, 0.36, 0.52]));
    const plate = new THREE.Mesh(
      new THREE.BoxGeometry(1.6, 0.08, 1.6),
      new THREE.MeshStandardMaterial({ color, roughness: 0.85, transparent: true, opacity: 0.75 }),
    );
    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(1.6, 0.08, 1.6)),
      new THREE.LineBasicMaterial({ color: 0x9f54ff, transparent: true, opacity: 0.55 }),
    );
    const pad = new THREE.Group();
    pad.add(plate, outline);
    return pad;
  }
  return null;
}

function ScenePreview({ revision, panelRef, spotlit }: {
  revision: number;
  panelRef?: React.Ref<HTMLElement>;
  spotlit?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("SCANNING STAGE...");

  useEffect(() => {
    if (!host.current) return;
    let disposed = false;
    let frame = 0;
    const container = host.current;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(3.2, 2.4, 4.2);
    // Without this the camera stares off past the city it is meant to frame.
    camera.lookAt(0, 0, 0);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xfff4d1, 0x190e27, 2.4));
    const key = new THREE.DirectionalLight(0xffc928, 3);
    key.position.set(3, 5, 2);
    scene.add(key);
    let model: THREE.Object3D;
    const fallback = new THREE.Group();
    fallback.add(
      new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshStandardMaterial({
        color: 0x19151f, emissive: 0x8428ff, emissiveIntensity: 0.45, roughness: 0.32, metalness: 0.75,
      })),
      new THREE.Mesh(new THREE.IcosahedronGeometry(1.12, 1), new THREE.MeshBasicMaterial({
        color: 0xffcb2e, wireframe: true, transparent: true, opacity: 0.65,
      })),
    );
    model = fallback;
    scene.add(fallback);
    setStatus("SCANNING STAGE...");
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0xffcb2e, transparent: true, opacity: 0.4,
    });
    fetch(`/api/world/scene?rev=${revision}`)
      .then((response) => response.json() as Promise<WorldScene>)
      .then((world) => {
        if (disposed) return;
        // Placement is never taught, so every district authors on the origin and
        // would otherwise render as one interpenetrating pile. The feed is a
        // planner's view: each district keeps its authored internal transforms
        // but is handed its own plot.
        const districts = new Map<string, ScenePrim[]>();
        for (const prim of world.prims) {
          const key = districtOf(prim.path);
          districts.set(key, [...(districts.get(key) || []), prim]);
        }
        const blocks = new THREE.Group();
        const built: THREE.Group[] = [];
        for (const [, members] of districts) {
          const block = new THREE.Group();
          // Rooms that never author a transform all land on the same spot, so
          // co-located neighbours get fanned apart. Anything the player did
          // place keeps exactly the position it authored.
          const spots = new Map<string, number>();
          for (const prim of members) {
            const geometry = prim.role === "geometry" ? primGeometry(prim) : null;
            const object = geometry
              ? new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
                color: new THREE.Color().setRGB(...(prim.color ?? [0.58, 0.54, 0.66])),
                roughness: 0.42,
                metalness: 0.28,
                emissive: new THREE.Color().setRGB(...(prim.color ?? [0.58, 0.54, 0.66])),
                emissiveIntensity: 0.09,
              }))
              : landmarkObject(prim);
            if (!object) continue;
            // USD hands back a row-major matrix for row-vector math, and fromArray
            // reads column-major, so the load itself performs the transpose.
            const placement = new THREE.Matrix4().fromArray(prim.matrix);
            object.applyMatrix4(placement);
            const at = new THREE.Vector3().setFromMatrixPosition(placement);
            const spot = `${at.x.toFixed(2)},${at.z.toFixed(2)}`;
            const taken = spots.get(spot) ?? 0;
            spots.set(spot, taken + 1);
            if (taken) {
              const ring = Math.ceil(taken / 8);
              const step = (taken - 1) * (Math.PI / 4);
              object.position.x += Math.cos(step) * 2.6 * ring;
              object.position.z += Math.sin(step) * 2.6 * ring;
            }
            object.userData.role = prim.role;
            block.add(object);
            if (geometry) {
              const outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), edgeMaterial);
              outline.applyMatrix4(placement);
              outline.position.copy(object.position);
              outline.userData.role = prim.role;
              block.add(outline);
            }
          }
          if (block.children.length) built.push(block);
        }
        if (!built.length) {
          setStatus("NO OPINIONS PUBLISHED YET");
          return;
        }
        // Size the plots from the largest district so nothing spills next door.
        let pitch = 0;
        const footprints = built.map((block) => {
          block.updateMatrixWorld(true);
          const box = new THREE.Box3().setFromObject(block);
          const size = box.getSize(new THREE.Vector3());
          pitch = Math.max(pitch, size.x, size.z);
          // Buildings are what rests on the pavement. A beacon's glow reaches
          // below its own centre, and letting that set the height would hoist
          // the whole district off the ground.
          const structural = new THREE.Box3();
          for (const child of block.children) {
            if (child.userData.role === "geometry") structural.expandByObject(child);
          }
          return { box, lift: structural.isEmpty() ? 0 : -structural.min.y };
        });
        pitch = (pitch || 2) * 1.55;
        const centres = planGrid(built.length, pitch);
        built.forEach((block, index) => {
          const { box, lift } = footprints[index];
          const centre = box.getCenter(new THREE.Vector3());
          block.position.set(centres[index].x - centre.x, lift, centres[index].z - centre.z);
          blocks.add(block);
        });
        const city = new THREE.Group();
        city.add(blocks);
        blocks.updateMatrixWorld(true);
        const extent = new THREE.Box3().setFromObject(blocks);
        const span = extent.getSize(new THREE.Vector3());
        // Centre the districts over the origin so the ground can be laid under
        // them. Only the footprint shifts; the skyline keeps standing on y=0.
        const centre = extent.getCenter(new THREE.Vector3());
        blocks.position.x -= centre.x;
        blocks.position.z -= centre.z;
        const ground = Math.max(span.x, span.z, pitch) * 1.3;
        const plate = new THREE.Mesh(
          new THREE.PlaneGeometry(ground, ground),
          new THREE.MeshStandardMaterial({ color: 0x1b1424, roughness: 0.95, metalness: 0 }),
        );
        plate.rotation.x = -Math.PI / 2;
        const lines = new THREE.GridHelper(ground, Math.max(4, built.length * 2), 0x6b4a9c, 0x33284a);
        (lines.material as THREE.Material).transparent = true;
        (lines.material as THREE.Material).opacity = 0.35;
        city.add(plate, lines);
        if (world.up_axis === "Z") city.rotation.x = -Math.PI / 2;
        // Frame on the ground plate, which always contains the districts, so a
        // single tall tower cannot shrink the rest of the city out of view.
        city.scale.multiplyScalar(4.3 / (Math.max(ground, span.y) * 1.42 || 1));
        city.updateMatrixWorld(true);
        const settled = new THREE.Box3().setFromObject(city).getCenter(new THREE.Vector3());
        city.position.set(-settled.x, -settled.y, -settled.z);
        scene.remove(fallback);
        model = city;
        scene.add(city);
        const counts = world.prims.reduce(
          (total, prim) => ({ ...total, [prim.role]: (total[prim.role] || 0) + 1 }),
          {} as Record<string, number>,
        );
        const parts = [
          counts.geometry ? `${counts.geometry} PRIM${counts.geometry === 1 ? "" : "S"}` : "",
          counts.light ? `${counts.light} LIGHT${counts.light === 1 ? "" : "S"}` : "",
          counts.pad ? `${counts.pad} LOT${counts.pad === 1 ? "" : "S"}` : "",
        ].filter(Boolean);
        setStatus(`${built.length} DISTRICT${built.length === 1 ? "" : "S"} · ${parts.join(" · ")}`);
      })
      .catch(() => setStatus("STAGE FEED OFFLINE"));
    const resize = () => {
      renderer.setSize(container.clientWidth, container.clientHeight, false);
      camera.aspect = container.clientWidth / Math.max(container.clientHeight, 1);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    const animate = () => {
      if (disposed) return;
      model.rotation.y += 0.006;
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, [revision]);

  return <section className={`preview-card panel ${spotlit ? "spotlight" : ""}`} ref={panelRef}>
    <div className="panel-heading"><span><Boxes size={15} /> CITY FEED</span><em>{status}</em></div>
    <div className="preview-viewport" ref={host}><div className="view-corners" /><span className="axis">Y ↑<br />X ↗</span></div>
    <div className="preview-meta"><span>STAGE: world/root.usda</span><span>PLAN VIEW</span><span>UP: Y</span></div>
  </section>;
}

function CensusReadout({ census }: { census: Census }) {
  const { stage, prims, observations, truncated } = census;
  const facts = [
    stage.default_prim ? `defaultPrim ${stage.default_prim}` : "no defaultPrim",
    stage.up_axis ? `upAxis ${stage.up_axis}` : "",
    stage.meters_per_unit ? `metersPerUnit ${stage.meters_per_unit}` : "",
    stage.sublayers?.length ? `sublayers: ${stage.sublayers.join(", ")}` : "no sublayers",
    stage.time_range ? `timeCode ${stage.time_range[0]}–${stage.time_range[1]}` : "",
  ].filter(Boolean);
  return <div className="census">
    {observations.length > 0 && <ul className="census-findings">{observations.map((item) => <li key={`${item.rule}:${item.target}:${item.observed}`}>
      <em>{item.target}</em>
      <span>{item.observed}</span>
    </li>)}</ul>}
    <div className="census-stage">{facts.join(" · ")}</div>
    {prims.length === 0 && <div className="census-stage">Your stage composed no prims at all.</div>}
    <ul className="census-tree">{prims.map((prim) => {
      // Depth is the path itself, so the tree reads without a nested walk.
      const depth = Math.max(prim.path.split("/").length - 2, 0);
      return <li key={prim.path} style={{ paddingLeft: `${depth * 9}px` }}>
        <b>{prim.specifier || "?"} {prim.type_name || "(untyped)"}</b>
        <span>{prim.path}</span>
        {(prim.kind || prim.flags.length > 0) && <small>{[prim.kind && `kind ${prim.kind}`, ...prim.flags].filter(Boolean).join(" · ")}</small>}
        {prim.properties.length > 0 && <i>{prim.properties.join(", ")}{prim.extra_properties > 0 ? ` +${prim.extra_properties} more` : ""}</i>}
      </li>;
    })}</ul>
    {truncated && <div className="census-stage">Stage larger than this readout; first {prims.length} prims shown.</div>}
  </div>;
}

export default function App() {
  const [state, setState] = useState<PlayerState>(emptyState);
  const [quests, setQuests] = useState<Quest[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [activeQuest, setActiveQuest] = useState<Quest | null>(null);
  const [code, setCode] = useState("");
  const [answers, setAnswers] = useState<Array<number | string>>([]);
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const tab = storedView().tab;
    return tab === "skills" || tab === "kiosk" ? tab : "map";
  });
  const [running, setRunning] = useState(false);
  const [assistBusy, setAssistBusy] = useState<"hint" | "census" | null>(null);
  const [assistResult, setAssistResult] = useState<AssistResult | null>(null);
  const [pendingSpend, setPendingSpend] = useState<"hint_tokens" | "prim_censuses" | null>(null);
  const [pendingReset, setPendingReset] = useState<ResetScope | null>(null);
  const [pendingBossRun, setPendingBossRun] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [checks, setChecks] = useState<boolean[]>([]);
  const [usdaView, setUsdaView] = useState<USDAView>({ before_usda: "", after_usda: "" });
  const [usdaMode, setUsdaMode] = useState<"before" | "after">("before");
  const [reviewPending, setReviewPending] = useState(false);
  const [revision, setRevision] = useState(0);
  const [toast, setToast] = useState<Toast | null>(null);
  const [showLanding, setShowLanding] = useState(() => {
    const remembered = storedView().landing;
    return typeof remembered === "boolean" ? remembered : localStorage.getItem(ONBOARDED_KEY) !== "1";
  });
  const [guideStep, setGuideStep] = useState<number | null>(null);
  const [mapScope, setMapScope] = useState<"floor" | "all">(() => storedView().scope === "all" ? "all" : "floor");
  const [browseFloor, setBrowseFloor] = useState<number | null>(() => {
    const floor = storedView().floor;
    return typeof floor === "number" ? floor : null;
  });
  const [pointer, setPointer] = useState<{ x: number; y: number; side: PointerSide } | null>(null);
  const [lessonOpen, setLessonOpen] = useState(false);
  const [, setLessonRevision] = useState(0);
  const booted = useRef(false);
  // Snapshot of the remembered view taken before anything can overwrite it.
  const bootView = useRef(storedView());
  // Unsaved edits per room, so stepping away and back mid-thought keeps the exact
  // buffer. Cleared work falls back to the server's saved submission on reload.
  const drafts = useRef(new Map<string, string>());
  const lessonRef = useRef<HTMLElement>(null);
  const editorRef = useRef<HTMLElement>(null);
  const focusEditor = useRef<(() => void) | null>(null);
  const runRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const usdaRef = useRef<HTMLElement>(null);
  const levelRef = useRef<HTMLSpanElement>(null);
  const payoutRef = useRef<HTMLElement>(null);
  const consumablesRef = useRef<HTMLElement>(null);
  const keyItemsRef = useRef<HTMLElement>(null);
  const feedRef = useRef<HTMLElement>(null);
  const recipesRef = useRef<HTMLDivElement>(null);
  const classRef = useRef<HTMLDivElement>(null);
  const saferoomRef = useRef<HTMLDivElement>(null);

  const refresh = async (advance = false) => {
    const firstBoot = !booted.current;
    const [nextState, nextQuests, nextRecipes] = await Promise.all([
      api<PlayerState>("/state"), api<Quest[]>("/quests"), api<Recipe[]>("/recipes"),
    ]);
    setState(nextState);
    setQuests(nextQuests);
    setRecipes(nextRecipes);
    if (advance) setBrowseFloor(null);
    setActiveQuest((current) => {
      const nextOpen = nextQuests.find((quest) => quest.unlocked && !quest.completed);
      const reviewId = localStorage.getItem(USDA_REVIEW_KEY);
      const reviewQuest = reviewId ? nextQuests.find((quest) => quest.id === reviewId) : null;
      if (!advance && reviewQuest) return reviewQuest;
      if (advance && nextOpen) return nextOpen;
      if (current) return nextQuests.find((quest) => quest.id === current.id) || current;
      if (firstBoot) {
        const remembered = bootView.current.questId;
        const rememberedQuest = remembered
          ? nextQuests.find((quest) => quest.id === remembered && quest.unlocked)
          : null;
        if (rememberedQuest) return rememberedQuest;
      }
      return nextOpen || nextQuests[0] || null;
    });
    // Only skip the intro automatically on the first load of a run in progress,
    // and only when the player has no remembered screen of their own. Reopening
    // it from the wordmark should stick until the player dismisses it.
    if (firstBoot) {
      booted.current = true;
      if (nextState.completed_quests.length > 0) {
        localStorage.setItem(ONBOARDED_KEY, "1");
        localStorage.setItem(GUIDED_KEY, "1");
        if (typeof bootView.current.landing !== "boolean") setShowLanding(false);
      }
    }
  };

  const chooseQuest = (quest: Quest) => {
    if (reviewPending && quest.id !== activeQuest?.id) {
      setUsdaMode("after");
      setToast({
        kind: "info",
        title: "REVIEW THE OPINION",
        message: "The room is clear. Inspect the updated USDA on the right, then continue.",
      });
      usdaRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    setBrowseFloor(quest.floor);
    setMapScope("floor");
    setActiveQuest(quest);
  };

  const openFloor = (floor: number | "all") => {
    if (floor === "all") {
      setMapScope("all");
      return;
    }
    setMapScope("floor");
    setBrowseFloor(floor);
  };

  const continueAfterReview = async () => {
    localStorage.removeItem(USDA_REVIEW_KEY);
    setReviewPending(false);
    setUsdaMode("before");
    await refresh(true);
  };

  const enterArena = () => {
    localStorage.setItem(ONBOARDED_KEY, "1");
    setShowLanding(false);
    setActiveTab("map");
    if (localStorage.getItem(GUIDED_KEY) !== "1") setGuideStep(0);
  };

  const closeGuide = () => {
    localStorage.setItem(GUIDED_KEY, "1");
    setGuideStep(null);
  };

  useEffect(() => {
    refresh().catch((error) => setToast({ kind: "error", title: "API OFFLINE", message: error.message }));
  }, []);
  useEffect(() => {
    // The room is omitted until one is resolved, otherwise the pre-boot null
    // would erase the room this load is still restoring.
    rememberView({
      landing: showLanding,
      tab: activeTab,
      floor: browseFloor,
      scope: mapScope,
      ...(activeQuest ? { questId: activeQuest.id } : {}),
    });
  }, [showLanding, activeTab, activeQuest?.id, browseFloor, mapScope]);
  useEffect(() => {
    if (!activeQuest) return;
    // A draft can legitimately be empty, so only it gets to short-circuit; an
    // unsaved room reports no submission and falls through to the starter.
    setCode(drafts.current.get(activeQuest.id) ?? (activeQuest.submission || activeQuest.starter || ""));
    setAnswers(activeQuest.questions?.map(() => "") || []);
    setAssistResult(null);
    setPendingSpend(null);
    setPendingBossRun(false);
    setChecks([]);
    const owesReview = localStorage.getItem(USDA_REVIEW_KEY) === activeQuest.id;
    setReviewPending(owesReview);
    setUsdaMode(activeQuest.completed || owesReview ? "after" : "before");
  }, [activeQuest?.id]);
  useEffect(() => {
    if (activeQuest) drafts.current.set(activeQuest.id, code);
  }, [activeQuest?.id, code]);
  useEffect(() => {
    if (!activeQuest) return;
    if (!showLanding && activeQuest.lesson && !activeQuest.completed && !lessonsRead().has(activeQuest.id)) {
      setLessonOpen(true);
    }
  }, [activeQuest?.id, showLanding]);
  useEffect(() => {
    if (!activeQuest) return;
    let cancelled = false;
    setUsdaView({ before_usda: "", after_usda: "" });
    api<USDAView>(`/quests/${activeQuest.id}/usda`)
      .then((view) => {
        if (!cancelled) setUsdaView(view);
      })
      .catch((error) => {
        if (!cancelled) {
          setToast({ kind: "error", title: "USDA OFFLINE", message: error.message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeQuest?.id]);
  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(timeout);
  }, [toast]);
  useEffect(() => {
    if (!lessonOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLessonOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [lessonOpen]);

  // Reveal what each step describes. Keyed on the step alone: reacting to
  // `lessonOpen` here would reopen the drawer the instant anyone closed it.
  useEffect(() => {
    if (guideStep === null) return;
    const target = GUIDE_STEPS[guideStep].target;
    // Some steps describe a tab, so the tour opens it for them. The closing step
    // returns to the map, which is where the player actually starts.
    const tab = ({ map: "map", recipes: "skills", class: "kiosk", saferoom: "kiosk", feed: "map" } as Record<string, Tab>)[target];
    if (tab) setActiveTab(tab);
    // The drawer covers the screen, so it has to step aside once the tour
    // moves on to the terminal behind it.
    setLessonOpen(target === "lesson");
  }, [guideStep]);

  // Park the arrow just outside the edge of whatever the tutorial is describing,
  // so the callout and the outline agree on the target.
  useEffect(() => {
    if (guideStep === null) {
      setPointer(null);
      return;
    }
    const target = GUIDE_STEPS[guideStep].target;
    const node = () => ({
      lesson: lessonRef.current,
      editor: editorRef.current,
      run: runRef.current,
      map: mapRef.current,
      usda: usdaRef.current,
      level: levelRef.current,
      payout: payoutRef.current,
      consumables: consumablesRef.current,
      keyitems: keyItemsRef.current,
      class: classRef.current,
      saferoom: saferoomRef.current,
      recipes: recipesRef.current,
      feed: feedRef.current,
    } as Record<GuideTarget, HTMLElement | null>)[target];
    const measure = () => {
      const rect = node()?.getBoundingClientRect();
      if (!rect || !rect.width) {
        setPointer(null);
        return;
      }
      const side = POINTER_SIDE[target];
      if (side === "up") {
        // Header targets sit above every panel, so the arrow tucks under them
        // and points back up rather than reaching in from a side.
        setPointer({
          x: Math.min(Math.max(rect.left + rect.width / 2, 60), window.innerWidth - 60),
          y: rect.bottom + 10,
          side,
        });
        return;
      }
      const centered = rect.top + Math.min(rect.height / 2, 150);
      const x = side === "left"
        ? Math.min(rect.right + 22, window.innerWidth - 104)
        : Math.max(108, rect.left - 10);
      let y = Math.min(Math.max(centered, 96), window.innerHeight - 44);
      // The tutorial card is fixed to the bottom left. Anything the arrow would
      // share that space with gets pointed at from higher up the target instead.
      const dock = document.querySelector(".guide-dock")?.getBoundingClientRect();
      const spansDock = dock && x - 96 < dock.right && x + 96 > dock.left;
      if (dock && spansDock && y + 20 > dock.top - 12) {
        y = Math.max(96, Math.min(y, dock.top - 44));
      }
      setPointer({ x, y, side });
    };
    // Narrow windows move the editor rail below the columns, so the run button
    // can start off-screen and take the fixed-position arrow with it.
    node()?.scrollIntoView({ block: target === "run" ? "center" : "nearest", inline: "nearest" });
    measure();
    const settle = window.setTimeout(measure, 280);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.clearTimeout(settle);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [guideStep, activeTab, lessonOpen]);

  const floors = useMemo(() => {
    const grouped = new Map<number, Quest[]>();
    quests.forEach((quest) => grouped.set(quest.floor, [...(grouped.get(quest.floor) || []), quest]));
    return [...grouped.entries()].sort(([a], [b]) => a - b);
  }, [quests]);
  const recipeGroups = useMemo(() => {
    const grouped = new Map<string, Recipe[]>();
    recipes.forEach((recipe) => grouped.set(recipe.category, [...(grouped.get(recipe.category) || []), recipe]));
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [recipes]);
  const masteredRecipes = recipes.filter((recipe) => recipe.unlocked).length;
  const nextQuest = useMemo(
    () => quests.find((quest) => quest.unlocked && !quest.completed) || null,
    [quests],
  );
  const nextPayingQuest = useMemo(
    () => quests.find((quest) => !quest.completed && quest.opinion_points > 0) || null,
    [quests],
  );
  const liveFloor = nextQuest?.floor ?? activeQuest?.floor ?? 0;
  const focusFloor = browseFloor ?? activeQuest?.floor ?? liveFloor;
  const visibleFloors = mapScope === "all" ? floors : floors.filter(([floor]) => floor === focusFloor);
  const focusRooms = floors.find(([floor]) => floor === focusFloor)?.[1] || [];
  const focusCleared = focusRooms.filter((quest) => quest.completed).length;
  const playbackEpisode = mapScope === "floor" && focusFloor !== liveFloor && focusCleared > 0;
  const playbackScene = Boolean(activeQuest?.completed && activeQuest.floor !== liveFloor);
  const reachableFloors = floors.filter(([, rooms]) => floorStatus(rooms) !== "locked");
  const archiveIndex = reachableFloors.findIndex(([floor]) => floor === focusFloor);
  const previousFloor = archiveIndex > 0 ? reachableFloors[archiveIndex - 1]?.[0] : undefined;
  const nextArchiveFloor = archiveIndex >= 0 ? reachableFloors[archiveIndex + 1]?.[0] : undefined;
  const resumeLiveBroadcast = () => {
    const live = nextQuest || quests.find((quest) => quest.unlocked && !quest.completed) || activeQuest;
    setBrowseFloor(null);
    setMapScope("floor");
    if (live && live.id !== activeQuest?.id && !reviewPending) setActiveQuest(live);
  };
  const lessonRead = activeQuest ? lessonsRead().has(activeQuest.id) : false;
  const spotlight = guideStep === null ? null : GUIDE_STEPS[guideStep].target;
  const xpFloor = (state.level - 1) * 100;
  const xpProgress = ((state.xp - xpFloor) / Math.max(state.next_level_xp - xpFloor, 1)) * 100;
  const liveBossFight = Boolean(
    activeQuest?.kind.endsWith("boss") && !activeQuest.completed && !playbackScene && !reviewPending,
  );
  const bossFee = activeQuest?.boss_fee ?? Math.min(25, Math.max(0, state.xp - xpFloor));
  const classPaths = state.class_benefits?.catalog?.length ? state.class_benefits.catalog : CLASS_PATHS;

  const runQuest = async () => {
    if (!activeQuest) return;
    setRunning(true);
    try {
      const result = await api<RunResult>(`/quests/${activeQuest.id}/run`, {
        method: "POST", body: JSON.stringify({ code, language: activeQuest.language, answers }),
      });
      setState(result.state);
      // Stage rules come back in the order the room declares them, so they line
      // up with the checklist as long as the stage opened at all.
      const stageChecks = result.results.filter((item) => !item.rule.startsWith("question_"));
      setChecks(stageChecks.length === activeQuest.expects.length ? stageChecks.map((item) => item.passed) : []);
      const payout = result.state.opinion_points - state.opinion_points;
      setUsdaView({
        before_usda: result.before_usda || usdaView.before_usda,
        after_usda: result.after_usda,
      });
      setUsdaMode(result.after_usda ? "after" : "before");
      const needsUsdaReview = result.success && activeQuest.language !== "none" && Boolean(result.after_usda);
      // Every clear publishes into world/root.usda, so the feed re-renders on
      // any win, not only the ones that open a USDA review.
      if (result.success) setRevision((value) => value + 1);
      if (needsUsdaReview) {
        setToast(null);
        localStorage.setItem(USDA_REVIEW_KEY, activeQuest.id);
        setReviewPending(true);
        window.setTimeout(() => usdaRef.current?.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
      } else if (!result.success) {
        setToast({
          kind: "error",
          title: "VALIDATION FAILED",
          message: `${result.system_message} ${result.results.filter((item) => !item.passed).map((item) => item.message).join(" ")}`,
        });
      }
      await refresh(result.success && !needsUsdaReview);
      if (needsUsdaReview && payout > 0) {
        setToast({
          kind: "info",
          title: `+${payout} OPINION POINT${payout === 1 ? "" : "S"}`,
          message: "Payout banked. Review the updated USDA before continuing.",
        });
      }
    } catch (error) {
      setToast({ kind: "error", title: "SIGNAL LOST", message: error instanceof Error ? error.message : "The API did not answer." });
    } finally {
      setRunning(false);
    }
  };

  const requestRun = () => {
    if (liveBossFight && !pendingBossRun) {
      setPendingBossRun(true);
      return;
    }
    setPendingBossRun(false);
    void runQuest();
  };

  const useHint = async () => {
    if (!activeQuest || assistBusy) return;
    setAssistBusy("hint");
    try {
      const result = await api<HintResponse>(`/quests/${activeQuest.id}/hint`, { method: "POST" });
      setState(result.state);
      setAssistResult({ kind: "hint", title: "SYSTEM HINT", message: result.hint });
    } catch (error) {
      setToast({
        kind: "error",
        title: "HINT DENIED",
        message: error instanceof Error ? error.message : "The System declined to elaborate.",
      });
    } finally {
      setAssistBusy(null);
    }
  };

  const readCensus = async () => {
    if (!activeQuest || assistBusy) return;
    setAssistBusy("census");
    try {
      const result = await api<CensusResponse>(`/quests/${activeQuest.id}/census`, { method: "POST" });
      setState(result.state);
      setAssistResult({ kind: "census", title: "PRIM CENSUS", census: result.census });
      await refresh();
    } catch (error) {
      setToast({
        kind: "error",
        title: "CENSUS DENIED",
        message: error instanceof Error ? error.message : "The registrar kept the ledger shut.",
      });
    } finally {
      setAssistBusy(null);
    }
  };

  const acknowledgeLesson = () => {
    if (!activeQuest) return;
    const read = lessonsRead();
    read.add(activeQuest.id);
    localStorage.setItem(LESSONS_READ_KEY, JSON.stringify([...read]));
    setLessonRevision((value) => value + 1);
    setLessonOpen(false);
    window.setTimeout(() => focusEditor.current?.(), 0);
  };

  const chooseClass = async (id: string) => {
    try {
      setState(await api<PlayerState>(`/specialization/${id}`, { method: "POST" }));
      setToast({
        kind: "success",
        title: "CLASS PATH LOCKED",
        message: `SYSTEM: ${id} recorded. Starter kit delivered. Home-floor perks are live. Still no skipped rooms and still no answers.`,
      });
    } catch (error) {
      setToast({ kind: "error", title: "PATH DENIED", message: error instanceof Error ? error.message : "The kiosk refused." });
    }
  };

  const runReset = async (scope: ResetScope) => {
    setPendingReset(null);
    setResetting(true);
    try {
      await api<PlayerState>(`/reset?scope=${scope}`, { method: "POST" });
      // Every panel is pointing at a city that no longer exists, so clear the
      // pointers before reloading. The review key especially: it would send
      // refresh() back to a room the wipe just un-cleared.
      localStorage.removeItem(USDA_REVIEW_KEY);
      if (scope === "all") {
        localStorage.removeItem(LESSONS_READ_KEY);
        // A city reset keeps the record, so saved source stays useful for reruns.
        // A full wipe un-clears every room, so the terminals go back to starters.
        drafts.current.clear();
      }
      setActiveQuest(null);
      setChecks([]);
      setReviewPending(false);
      setUsdaView({ before_usda: "", after_usda: "" });
      setAssistResult(null);
      setLessonOpen(false);
      setActiveTab("map");
      // refresh() is the one path that reloads state, quests, and recipes
      // together and opens the next room, which is what a boot would do.
      await refresh(true);
      setRevision((value) => value + 1);
      setToast({
        kind: "success",
        title: scope === "all" ? "CRAWL RESET" : "CITY DEMOLISHED",
        message: scope === "all"
          ? "SYSTEM: Save wiped and the skyline with it. Floor 00 is taping again."
          : "SYSTEM: Every published layer is gone. Your record stands — rerun any episode to rebuild its block.",
      });
    } catch (error) {
      setToast({
        kind: "error",
        title: "RESET REFUSED",
        message: error instanceof Error ? error.message : "The System kept the tapes.",
      });
    } finally {
      setResetting(false);
    }
  };

  const buyUpgrade = async (id: string) => {
    try {
      const next = await api<PlayerState>(`/shop/${id}`, { method: "POST" });
      setState(next);
      const restock = next.shop[id]?.kind === "consumable";
      setToast({
        kind: "success",
        title: restock ? "CONSUMABLE RESTOCKED" : "UPGRADE INSTALLED",
        message: restock
          ? "Delivered to Consumables on the left rail. Saferoom restocks are final."
          : "No refunds after the screaming starts.",
      });
    } catch (error) {
      setToast({ kind: "error", title: "PURCHASE DENIED", message: error instanceof Error ? error.message : "The kiosk ate your points." });
    }
  };

  const tradeTrophies = async (id: string) => {
    try {
      const result = await api<CurioResponse>(`/curio/${id}`, { method: "POST" });
      setState(result.state);
      const stampedNames = Object.entries(result.stamped)
        .map(([name, count]) => `${name.replaceAll("_", " ")}${count > 1 ? ` ×${count}` : ""}`)
        .join(", ");
      setToast({
        kind: "success",
        title: "TROPHIES STAMPED",
        message: `The desk stamped ${stampedNames} and restocked Consumables. You keep the trophies; only their trade value is gone.`,
      });
    } catch (error) {
      setToast({
        kind: "error",
        title: "DESK DECLINED",
        message: error instanceof Error ? error.message : "The appraiser went to lunch.",
      });
    }
  };

  const inventory = Object.entries(state.inventory);
  const hintTokens = state.inventory.hint_tokens || 0;
  const primCensuses = state.inventory.prim_censuses || 0;
  const consumables = [
    { id: "hint_tokens" as const, quantity: hintTokens, cost: state.shop?.hint_refill?.cost },
    { id: "prim_censuses" as const, quantity: primCensuses, cost: state.shop?.prim_census?.cost },
  ];
  const keyItems = inventory.filter(([name]) => name !== "hint_tokens" && name !== "prim_censuses");
  const stampedItems = state.stamped_items || {};
  const trophiesHeld = keyItems.reduce((total, [, quantity]) => total + quantity, 0);
  const trophiesUnstamped = state.curio?.unstamped
    ?? keyItems.reduce((total, [name, quantity]) => total + Math.max(quantity - (stampedItems[name] || 0), 0), 0);
  const curioOffers = Object.entries(state.curio?.offers || {});
  const shopSections = [
    { id: "consumable" as const, heading: "CONSUMABLES // RESTOCK HERE", items: Object.entries(state.shop || {}).filter(([, item]) => item.kind === "consumable") },
    { id: "upgrade" as const, heading: "UPGRADES // PERMANENT AND COSMETIC", items: Object.entries(state.shop || {}).filter(([, item]) => item.kind !== "consumable") },
  ];
  const status = activeQuest ? questStatus(activeQuest) : "locked";
  const visibleUsda = usdaMode === "before" ? usdaView.before_usda : usdaView.after_usda;

  if (showLanding) {
    return <div className="app-shell">
      <Landing
        onStart={enterArena}
        hasProgress={state.completed_quests.length > 0}
        nextQuest={nextQuest}
        quests={quests}
        floors={floors}
      />
      {toast && <div className="system-toast error"><div className="toast-tag">SYSTEM // ALERT</div><strong>{toast.title}</strong><p>{toast.message}</p></div>}
    </div>;
  }

  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => setShowLanding(true)} title="Replay the intro">
        <div className="brand-mark"><span>P</span></div>
        <div><strong>PRIMVENTURE</strong><small>{playbackEpisode || playbackScene ? "SYNDICATED RERUN" : "THE COMPOSITION IS LIVE"}</small></div>
      </button>
      <div className={`broadcast ${playbackEpisode || playbackScene ? "rerun" : ""}`}>
        {playbackEpisode || playbackScene
          ? <><span className="live-dot rerun" /> PLAYBACK <b>{episodeCode(playbackScene ? activeQuest!.floor : focusFloor)}</b></>
          : <><span className="live-dot" /> ON AIR <b>{episodeCode(liveFloor)}</b></>}
      </div>
      <div className="player-strip">
        <button className="help-button" onClick={() => setGuideStep(0)}><HelpCircle size={14} /> HOW TO PLAY</button>
        <div className="avatar">{state.contestant.slice(-2)}</div><div><small>{state.title}</small><strong>{state.contestant}</strong></div>
        <span className={`level ${spotlight === "level" ? "spotlight" : ""}`} ref={levelRef}>LVL {state.level}</span>
      </div>
    </header>
    <main>
      <aside className="left-rail">
        <section className={`player-card panel ${spotlight === "payout" ? "spotlight" : ""}`} ref={payoutRef}>
          <div className="panel-heading"><span><Swords size={15} /> RUN STATUS</span><em>{state.completed_quests.length}/{quests.length}</em></div>
          <div className="stat-line"><span><Trophy size={15} /> CITY CONTROL</span><b>{quests.length ? Math.round(state.completed_quests.length / quests.length * 100) : 0}%</b></div>
          <div className="meter health"><i style={{ width: `${quests.length ? state.completed_quests.length / quests.length * 100 : 0}%` }} /></div>
          <div className="stat-line"><span><Zap size={15} /> EXPERIENCE</span><b>{state.xp}/{state.next_level_xp}</b></div>
          <div className="meter xp"><i style={{ width: `${xpProgress}%` }} /></div>
          <p className="currency-note">
            Each room pays its XP once, and <b>100 XP</b> is a level. Some rooms stay shut below a
            level. Losing to a boss costs XP, never a level.
          </p>
          <div className="currency"><CircleDollarSign size={18} /><div><small>OPINION POINTS</small><b>{state.opinion_points}</b></div></div>
          <p className="currency-note">
            Earned by clearing boss rooms. {nextPayingQuest
              ? <>Next payout: <b>{nextPayingQuest.title}</b> (+{nextPayingQuest.opinion_points} OP).</>
              : "Every paying room on this route is cleared."}
          </p>
          {(state.specialization || state.level >= 2) && <div className="stat-line"><span><Shield size={15} /> CLASS PATH</span><b>{state.specialization || "UNDECLARED"}</b></div>}
          {state.specialization && state.class_benefits?.home_names?.length ? <p className="currency-note">Home floors: {state.class_benefits.home_names.join(", ")}. Perks never skip a room or reveal an answer.</p> : null}
        </section>
        <section className={`inventory panel ${spotlight === "consumables" ? "spotlight" : ""}`} ref={consumablesRef}>
          <div className="panel-heading"><span><FlaskConical size={15} /> CONSUMABLES</span><button className="restock-link" onClick={() => setActiveTab("kiosk")}>SAFEROOM</button></div>
          {consumables.map(({ id, quantity, cost }) => {
            const isHint = id === "hint_tokens";
            const censusArmed = Boolean(activeQuest?.census_armed);
            // A census already paid for on this fail stays readable for free.
            const censusPaid = Boolean(activeQuest?.census_paid);
            const classFree = Boolean(isHint ? activeQuest?.free_hint : activeQuest?.free_census && censusArmed);
            const settled = !isHint && censusPaid;
            const unavailable = (!classFree && !settled && quantity < 1) || assistBusy !== null || (!isHint && !censusArmed);
            const label = isHint ? "Hint Token" : "Prim Census";
            const short = isHint ? "Hint" : "Census";
            const detail = settled
              ? "PAID FOR THIS RUN · tap to re-read"
              : classFree
              ? "CLASS PERK · this use is free"
              : quantity < 1
              ? `Out of stock · ${cost ?? "?"} OP in Saferoom`
              : isHint
                ? "Tap to use · clue for this room"
                : censusArmed
                  ? "Tap to use · lists the prims your stage actually composed"
                  : activeQuest?.completed
                    ? "Cleared rooms do not consume a census"
                    : "Fail this room first · then it reports your real stage";
            const icon = (isHint && assistBusy === "hint") || (!isHint && assistBusy === "census")
              ? <RefreshCw className="spin" />
              : isHint ? <Lightbulb size={17} /> : <ListTree size={17} />;
            // Re-reading a census already paid for costs nothing, so it skips
            // the confirm step that exists to guard an irreversible spend.
            if (settled) {
              return <button
                className="inventory-item usable"
                key={id}
                disabled={assistBusy !== null}
                onClick={() => void readCensus()}
                title={detail}
              >
                <span className="item-icon epic">{icon}</span>
                <div><strong>{label}</strong><small>{detail}</small></div>
                <b>{quantity} LEFT</b>
              </button>;
            }
            // Spending is irreversible, so the first click only arms the item.
            if (pendingSpend === id) {
              return <div className={`inventory-item confirming ${classFree ? "class-free" : ""}`} key={id}>
                <span className={`item-icon ${isHint ? "rare" : "epic"}`}>{icon}</span>
                <div><strong>{classFree ? `Use free ${short}?` : `Spend 1 ${short}?`}</strong><small>{classFree ? "Class perk. Inventory stays put." : `${quantity - 1} would be left`}</small></div>
                <div className="confirm-actions">
                  <button className="yes" onClick={() => { setPendingSpend(null); (isHint ? useHint : readCensus)(); }}>{classFree ? "USE FREE" : "SPEND"}</button>
                  <button className="no" onClick={() => setPendingSpend(null)} aria-label={`Keep the ${label}`}><X size={13} /></button>
                </div>
              </div>;
            }
            return <button
              className={`inventory-item usable ${classFree ? "class-free" : ""}`}
              key={id}
              disabled={unavailable}
              onClick={() => setPendingSpend(id)}
              title={detail}
            >
              <span className={`item-icon ${isHint ? "rare" : "epic"}`}>{icon}</span>
              <div><strong>{label}</strong><small>{detail}</small></div>
              <b>{quantity} LEFT</b>
            </button>;
          })}
          {consumables.some((item) => item.quantity < 1) && <p className="currency-note">
            Restocking costs Opinion Points, and boss rooms are what pay them out. You have <b>{state.opinion_points} OP</b>.
          </p>}
          {assistResult && <div className={`assist-result ${assistResult.kind}`}>
            <button onClick={() => setAssistResult(null)} aria-label="Dismiss assistance"><X /></button>
            <span>{assistResult.title}</span>
            {assistResult.census
              ? <CensusReadout census={assistResult.census} />
              : <p>{assistResult.message}</p>}
          </div>}
        </section>
        <section className={`inventory panel key-items ${spotlight === "keyitems" ? "spotlight" : ""}`} ref={keyItemsRef}>
          <div className="panel-heading">
            <span><Backpack size={15} /> KEY ITEMS</span>
            {trophiesUnstamped > 0
              ? <button className="restock-link" onClick={() => setActiveTab("kiosk")}>CURIO DESK</button>
              : <em>{keyItems.length}</em>}
          </div>
          {keyItems.map(([name, quantity]) => {
            const used = stampedItems[name] || 0;
            return <div className={`inventory-item passive ${used >= quantity ? "stamped" : ""}`} key={name}>
              <span className="item-icon legendary"><Backpack size={17} /></span>
              <div><strong>{name.replaceAll("_", " ")}</strong><small>{used
                ? `Room-clear trophy · ${used} of ${quantity} stamped`
                : "Room-clear trophy · trade value unspent"}</small></div>
              <b>× {quantity}</b>
            </div>;
          })}
          <p className="currency-note"><b>{trophiesUnstamped}</b> available to trade</p>
        </section>
        <ScenePreview revision={revision} panelRef={feedRef} spotlit={spotlight === "feed"} />
      </aside>
      <section className="command-center">
        <nav className="mode-tabs">
          <button className={activeTab === "map" ? "active" : ""} onClick={() => setActiveTab("map")}><Skull size={16} /> DUNGEON MAP</button>
          <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}><Sparkles size={16} /> RECIPE TREE</button>
          <button className={activeTab === "kiosk" ? "active" : ""} onClick={() => setActiveTab("kiosk")}><ShoppingCart size={16} /> SAFEROOM</button>
        </nav>
        {activeTab === "map" && <div className={`map panel ${playbackEpisode ? "playback" : ""} ${spotlight === "map" ? "spotlight" : ""}`} ref={mapRef}>
          <div className="map-title">
            <div>
              <span>{mapScope === "floor"
                ? `${playbackEpisode ? "PLAYBACK EPISODE" : "LIVE BROADCAST"} · ${episodeCode(focusFloor)} · ${focusCleared}/${focusRooms.length} SCENES`
                : "SEASON 01 · BOX SET"}</span>
              <h1>{mapScope === "floor" ? focusRooms[0]?.floor_name || "RECAPTURE PROTOCOL" : "SEASON GUIDE"}</h1>
              <p>{playbackEpisode
                ? <>Previously on the Composition. The audience is rewatching this episode while the live crawl waits on floor {String(liveFloor).padStart(2, "0")}.{nextQuest ? <> Resume with <b>{nextQuest.title}</b>.</> : null}</>
                : nextQuest
                  ? <>This episode is still taping. Clear the rooms, face the boss, and the System files another syndication package. Next scene: <b>{nextQuest.title}</b>.</>
                  : "Season finale locked. Every episode is in the can."}</p>
              <div className="episode-guide" aria-label="Season 01 episode guide">
                <button className="episode-step" disabled={previousFloor === undefined} onClick={() => previousFloor !== undefined && openFloor(previousFloor)} aria-label="Previous episode">
                  <ChevronLeft size={14} />
                </button>
                {floors.map(([floor, rooms]) => {
                  const kind = floorStatus(rooms);
                  const selected = mapScope === "floor" && floor === focusFloor;
                  return <button
                    key={floor}
                    className={`episode-chip ${kind} ${selected ? "active" : ""}`}
                    disabled={kind === "locked"}
                    onClick={() => openFloor(floor)}
                    title={`${episodeTag(kind)} · ${episodeCode(floor)} · ${rooms[0]?.floor_name}`}
                  >
                    <em>EP</em>
                    {String(floor).padStart(2, "0")}
                    <small>{episodeTag(kind)}</small>
                  </button>;
                })}
                <button className="episode-step" disabled={nextArchiveFloor === undefined} onClick={() => nextArchiveFloor !== undefined && openFloor(nextArchiveFloor)} aria-label="Next episode">
                  <ChevronRight size={14} />
                </button>
                <button className={`episode-chip all ${mapScope === "all" ? "active" : ""}`} onClick={() => openFloor("all")}>BOX SET</button>
              </div>
            </div>
            <div className="completion"><b>{state.completed_quests.length}/{quests.length}</b><small>SCENES FILED</small></div>
          </div>
          {playbackEpisode && <div className="playback-bumper">
            <div className="bumper-bug"><i className="rec-dot" /> RERUN</div>
            <Clapperboard size={22} />
            <div>
              <span>PREVIOUSLY ON THE COMPOSITION</span>
              <strong>{episodeCode(focusFloor)} · {focusRooms[0]?.floor_name}</strong>
              <p>
                SYSTEM: This episode already aired. The crowd demanded a recap package, so here we are, watching you watch yourself.
                Open a scene to reread the lesson and the USDA on file. Nothing here advances the live crawl.
              </p>
            </div>
            <button className="resume-live" onClick={resumeLiveBroadcast}>RESUME LIVE BROADCAST</button>
          </div>}
          <div className="floor-list">{visibleFloors.map(([floor, rooms]) => <div className="floor" key={floor}>
            <div className="floor-label"><span>{episodeCode(floor)} · {floorStatus(rooms) === "cleared" ? "RERUN" : floorStatus(rooms) === "live" ? "ON AIR" : "UNAIRED"}</span><strong>{rooms[0]?.floor_name}</strong></div>
            <div className="room-track">{rooms.map((quest, index) => {
              const roomStatus = questStatus(quest);
              return <div className="room-wrap" key={quest.id}>
                {index > 0 && <span className={`connector ${roomStatus === "locked" ? "locked" : ""}`} />}
                <button className={`room ${roomStatus} ${activeQuest?.id === quest.id ? "selected" : ""}`} disabled={roomStatus === "locked"} onClick={() => chooseQuest(quest)}>
                  {roomStatus === "locked" ? <LockKeyhole /> : roomStatus === "boss" ? <Skull /> : roomStatus === "complete" ? <Trophy /> : <Code2 />}
                  <span>{quest.kind.endsWith("boss") ? "BOSS" : `0${index + 1}`}</span>
                </button><small>{quest.title}</small>
                {quest.opinion_points > 0 && <b className={`room-pay ${roomStatus === "complete" ? "spent" : ""}`}>{roomStatus === "complete" ? `PAID ${quest.opinion_points} OP` : `+${quest.opinion_points} OP`}</b>}
              </div>;
            })}</div>
          </div>)}</div>
          <div className="legend"><span><i className="complete" /> AIRED</span><span><i className="available" /> TAPING</span><span><i className="boss" /> FINALE</span><span><i className="locked" /> UNAIRED</span><span>RERUN PLAYS BACK A CLEARED EPISODE FOR THE AUDIENCE</span></div>
        </div>}
        {activeTab === "skills" && <div className={`skill-tree panel ${spotlight === "recipes" ? "spotlight" : ""}`} ref={recipesRef}>
          <div className="section-hero"><span>THE COOKBOOK INDEX</span><h1>RECIPES OF POWER</h1><p>Glossary nodes from the Cookbook graph. Clear rooms that name them. SYSTEM: collecting terms fills the shelf; composing them builds the city.</p><small className="recipe-count">{masteredRecipes}/{recipes.length} MASTERED</small></div>
          {recipeGroups.map(([category, nodes]) => <section className="recipe-cluster" key={category}>
            <header><span>{category.replaceAll("-", " ")}</span><b>{nodes.filter((node) => node.unlocked).length}/{nodes.length}</b></header>
            <div className="skill-grid">{nodes.map((recipe, index) => <article className={`skill-node ${recipe.unlocked ? "unlocked" : ""} ${recipe.affinity ? "affinity" : ""}`} key={recipe.id} style={{ "--i": index } as React.CSSProperties}>
              <span className="skill-gem">{recipe.unlocked ? <Gem /> : <LockKeyhole />}</span><small>{recipe.category.replaceAll("-", " ")}</small><h3>{recipe.label}</h3><p>{recipe.unlocked ? "Authored in a cleared room. Keep the composed result inspectable." : "Undiscovered. Win a room that names this term."}</p><footer>{recipe.affinity ? "CLASS AFFINITY" : recipe.unlocked ? "MASTERED" : "UNDISCOVERED"}</footer>
            </article>)}</div>
          </section>)}
        </div>}
        {activeTab === "kiosk" && <div className={`kiosk panel ${spotlight === "saferoom" ? "spotlight" : ""}`} ref={saferoomRef}>
          <div className="section-hero"><span>SAFEROOM KIOSK // OPINIONS FINAL</span><h1>SPEND TO SURVIVE</h1><p>SYSTEM: Everything here costs Opinion Points, and Opinion Points come from clearing boss rooms. {nextPayingQuest ? `Your next payout is ${nextPayingQuest.title}, worth ${nextPayingQuest.opinion_points}.` : "You have cleared every paying room on this route."} Consumables land in the left rail. Upgrades never clear rooms for you.</p><small className="recipe-count">{state.opinion_points} OP BANKED</small></div>
          <div className={`class-choice ${spotlight === "class" ? "spotlight" : ""}`} ref={classRef}>
            <div className="class-explainer">
              <span>CLASS PATH // AVAILABLE AT LEVEL 2</span>
              <p>
                Declare a discipline. You get a starter kit, cheaper restocks, extra Opinion Points
                on that path's home floors, and a softer boss fee there. Classes never skip rooms
                or reveal answers. A full crawl reset is the only way to choose again.
              </p>
            </div>
            <div className="class-grid">{classPaths.map((path) => {
            const selected = state.specialization === path.id;
            const lockedOut = Boolean(state.specialization) && !selected;
            const tooSoon = state.level < 2;
            return <article className={selected ? "owned" : ""} key={path.id}>
              <Shield size={34} /><h3>{path.title}</h3><p>{path.blurb}</p>
              <small className="class-kit">{path.kit}</small>
              <ul className="class-perks">{path.perks.map((perk) => <li key={perk}>{perk}</li>)}</ul>
              <button disabled={selected || lockedOut || tooSoon} onClick={() => chooseClass(path.id)}>
                {selected ? "DECLARED" : tooSoon ? "LEVEL 2 REQUIRED" : lockedOut ? "PATH CLOSED" : "DECLARE PATH"}
              </button>
            </article>;
            })}</div>
          </div>
          {shopSections.map((section) => <div className="shop-section" key={section.id}>
            <div className="shop-heading">{section.heading}</div>
            <div className="shop-grid">{section.items.map(([id, item], index) => {
              const owned = state.upgrades.includes(id) && !item.repeatable;
              return <article className={owned ? "owned" : ""} key={id}><div className="shop-number">0{index + 1}</div>{item.kind === "consumable" ? <FlaskConical size={34} /> : <Shield size={34} />}<h3>{item.name}</h3><p>{item.description}</p>
                <button disabled={owned || state.opinion_points < item.cost} onClick={() => buyUpgrade(id)}>{owned ? "INSTALLED" : state.opinion_points < item.cost ? `NEED ${item.cost - state.opinion_points} MORE OP` : item.repeatable ? <><CircleDollarSign size={15} /> {item.cost} OP · RESTOCK</> : <><CircleDollarSign size={15} /> {item.cost} OP</>}</button>
              </article>;
            })}</div>
          </div>)}
          {curioOffers.length > 0 && <div className="shop-section curio-desk">
            <div className="shop-heading">CURIO DESK // PAY IN KEY ITEMS, NOT OP</div>
            <div className="shop-grid">{curioOffers.map(([id, offer], index) => {
              const short = offer.trophy_cost - trophiesUnstamped;
              const grant = Object.entries(offer.inventory)
                .map(([item, count]) => item === "hint_tokens" ? `${count} Hint Token${count === 1 ? "" : "s"}` : `${count} Prim Census${count === 1 ? "" : "es"}`)
                .join(" and ");
              return <article key={id}>
                <div className="shop-number">0{index + 1}</div><Backpack size={34} />
                <h3>{offer.name}</h3>
                <p>Hand over {offer.trophy_cost} unstamped Key Items for {grant}. The appraiser stamps each trophy and gives it back, so your record of cleared rooms stays whole.</p>
                <button disabled={short > 0} onClick={() => tradeTrophies(id)}>
                  {short > 0
                    ? `NEED ${short} MORE UNSTAMPED`
                    : <><Backpack size={15} /> {offer.trophy_cost} TROPHIES · TRADE</>}
                </button>
              </article>;
            })}</div>
            <small className="fine-print">
              {trophiesUnstamped} of your {trophiesHeld} trophies are unstamped. Clearing an
              ordinary room earns one; bosses pay Opinion Points instead. The desk trades for
              supplies only, so it can never buy an upgrade or skip a room.
            </small>
          </div>}
          <div className="shop-section danger-zone">
            <div className="shop-heading">CONDEMNED // NO REFUNDS, NO UNDO</div>
            <div className="shop-grid">
              {RESET_OPTIONS.map((option) => {
                const armed = pendingReset === option.scope;
                return <article className={armed ? "arming" : ""} key={option.scope}>
                  <div className="shop-number">{option.scope === "city" ? "01" : "02"}</div>
                  {option.scope === "city" ? <Building2 size={34} /> : <Skull size={34} />}
                  <h3>{option.title}</h3>
                  <p>{armed ? option.confirm : option.blurb}</p>
                  {armed
                    ? <div className="confirm-actions">
                      <button className="yes" disabled={resetting} onClick={() => runReset(option.scope)}>
                        {resetting ? <RefreshCw className="spin" size={15} /> : <Trash2 size={15} />} {option.action}
                      </button>
                      <button className="no" onClick={() => setPendingReset(null)} aria-label="Keep everything"><X size={13} /></button>
                    </div>
                    // Nothing here is recoverable, so the first click only arms it.
                    : <button disabled={resetting} onClick={() => setPendingReset(option.scope)}>{option.action}</button>}
                </article>;
              })}
            </div>
          </div>
          <small className="fine-print">*Saferoom status void during syntax errors and certification deadlines.</small>
        </div>}
        <section className={`authoring-dock code-panel panel ${spotlight === "editor" ? "spotlight" : ""}`} ref={editorRef}>
          <div className="editor-toolbar">
            <span><TerminalSquare size={15} /> {playbackScene ? "PLAYBACK TERMINAL" : "ROOM TERMINAL"}</span>
            <div><button className="active">{activeQuest?.language.toUpperCase() || "—"}</button></div>
          </div>
          <Editor
            height="100%"
            language={activeQuest?.language === "python" ? "python" : "plaintext"}
            theme="vs-dark"
            value={code}
            onChange={(value) => setCode(value || "")}
            onMount={(editor) => { focusEditor.current = () => editor.focus(); }}
            options={{ readOnly: activeQuest?.language === "none" || reviewPending, minimap: { enabled: false }, fontSize: 13, lineHeight: 21, padding: { top: 16 }, scrollBeyondLastLine: false, tabSize: 4 }}
          />
          <div className="run-slot" ref={runRef}>
            {pendingBossRun && liveBossFight
              ? <div className={`boss-confirm ${spotlight === "run" ? "spotlight" : ""}`}>
                  <span>READY TO CHALLENGE?</span>
                  <p>
                    {bossFee > 0
                      ? <>A wrong answer costs <b>{bossFee} XP</b>{activeQuest?.boss_fee_kind === "home" ? " (class rate: half)" : ""}. Your level stays {state.level}. </>
                      : activeQuest?.boss_fee_kind === "waiver"
                        ? <>Exchanger waiver: this first Customs miss costs no XP. Your level stays {state.level}. </>
                        : <>You're on the floor of this level, so a miss costs no XP this time. </>}
                    A clear is the only way onto the next room. Are you sure you're ready?
                  </p>
                  <div className="confirm-actions">
                    <button className="yes" onClick={requestRun} disabled={running}>
                      {running ? <RefreshCw className="spin" /> : <Skull />} I'M READY · CHALLENGE THE BOSS
                    </button>
                    <button className="no" onClick={() => setPendingBossRun(false)} disabled={running}>NOT YET</button>
                  </div>
                </div>
              : <button className={`run-button ${running ? "is-running" : ""} ${liveBossFight ? "boss" : ""} ${spotlight === "run" ? "spotlight" : ""}`} onClick={requestRun} disabled={running || !activeQuest || status === "locked" || reviewPending}>
                  {running ? <RefreshCw className="spin" /> : reviewPending ? <CheckCircle2 /> : liveBossFight ? <Skull /> : <Play fill="currentColor" />} {running ? "JUDGES ARE THINKING..." : reviewPending ? "ROOM CLEARED — REVIEW USDA →" : playbackScene ? "RERUN THIS SCENE" : activeQuest?.language === "none" ? "ACKNOWLEDGE BRIEF" : liveBossFight ? "CHALLENGE THE BOSS" : "RUN THE ROOM"}
                </button>}
          </div>
        </section>
      </section>
      <aside className="editor-rail">
        <section className="challenge-card">
          <div className="eyebrow"><span>{playbackScene ? "PLAYBACK SCENE · " : "LIVE · "}{activeQuest?.kind.replaceAll("_", " ").toUpperCase() || "NO SIGNAL"}</span><b>+{activeQuest?.xp || 0} XP{activeQuest?.opinion_points ? ` · +${activeQuest.opinion_points} OP` : ""}</b></div>
          <h2>{activeQuest?.title || "Waiting for the System"}</h2><p>{activeQuest?.brief}</p>
          {playbackScene && activeQuest && <p className="playback-note">Originally aired as {episodeCode(activeQuest.floor)}. The audience is watching the recap. Your live assignment has not moved.</p>}
          <div className="objective"><ChevronRight size={16} /><span><small>NEIGHBORHOOD</small>{activeQuest?.neighborhood}</span></div>
          {activeQuest && <div className="learning-route">
            <span className={lessonRead ? "done" : ""}><b>1</b> LEARN</span><i />
            <span className={reviewPending ? "done" : "current"}><b>2</b> AUTHOR</span><i />
            <span className={reviewPending ? "done" : checks.length ? "current" : ""}><b>3</b> VALIDATE</span><i />
            <span className={reviewPending ? "current" : ""}><b>4</b> REVIEW</span>
          </div>}
          {playbackScene && <button className="resume-live card" onClick={resumeLiveBroadcast}>
            <Tv size={14} /> BACK TO THE LIVE BROADCAST
          </button>}
          {activeQuest && <button className="cookbook-link" onClick={() => setLessonOpen(true)}><BookOpen size={15} /> {playbackScene ? "REWATCH THE BRIEFING" : lessonRead ? "REVIEW LESSON" : "LEARN THIS ROOM"}</button>}
          {activeQuest && activeQuest.expects.length > 0 && <div className="expectations">
            <span className="expect-heading"><ListChecks size={14} /> THE TERMINAL CHECKS FOR</span>
            <ol>{activeQuest.expects.map((line, index) => {
              const verdict = checks[index];
              return <li className={verdict === undefined ? "" : verdict ? "passed" : "failed"} key={line}>
                <i>{verdict === undefined ? <Circle size={12} /> : verdict ? <CheckCircle2 size={12} /> : <XCircle size={12} />}</i>
                <span>{line}</span>
              </li>;
            })}</ol>
          </div>}
          {activeQuest?.questions?.map((question, index) => <label className="boss-question" key={question.prompt}>{question.prompt}
            {question.choices?.length ? <select value={String(answers[index] ?? "")} onChange={(event) => setAnswers((current) => current.map((answer, i) => i === index ? Number(event.target.value) : answer))}>
              <option value="">Choose…</option>{question.choices.map((choice, choiceIndex) => <option value={choiceIndex} key={choice}>{choice}</option>)}
            </select> : <input value={String(answers[index] ?? "")} onChange={(event) => setAnswers((current) => current.map((answer, i) => i === index ? event.target.value : answer))} placeholder="Explain your reasoning…" />}
          </label>)}
        </section>
        <section className={`usda-panel panel ${reviewPending ? "review-required" : ""} ${spotlight === "usda" ? "spotlight" : ""}`} ref={usdaRef}>
          <div className="usda-heading">
            <span><Code2 size={15} /> {playbackScene ? "FILED USDA · ORIGINAL AIR" : "AUTHORED USDA"}</span>
            <div className="usda-tabs">
              <button className={usdaMode === "before" ? "active" : ""} onClick={() => setUsdaMode("before")}>BEFORE</button>
              <button className={usdaMode === "after" ? "active" : ""} onClick={() => setUsdaMode("after")} disabled={!usdaView.after_usda}>AFTER</button>
            </div>
          </div>
          {reviewPending && <div className="review-callout">
            <ArrowRight size={18} />
            <div><strong>ROOM CLEARED // REVIEW THE UPDATE</strong><small>The green USDA is the layer your Python authored.</small></div>
          </div>}
          <div className={`usda-editor ${usdaMode}`}>
            {visibleUsda ? <Editor
              key={`${activeQuest?.id}-${usdaMode}-${reviewPending ? "review" : "idle"}`}
              height="100%"
              language="plaintext"
              theme="vs-dark"
              value={visibleUsda}
              onMount={(editor) => {
                if (usdaMode !== "after" || !usdaView.before_usda) return;
                const line = firstChangedLine(usdaView.before_usda, usdaView.after_usda);
                editor.revealLineInCenter(line);
                editor.deltaDecorations([], [{
                  range: { startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: 1 },
                  options: { isWholeLine: true, className: "usda-changed-line", glyphMarginClassName: "usda-changed-glyph" },
                }]);
              }}
              options={{ readOnly: true, minimap: { enabled: false }, fontSize: 11, lineHeight: 18, wordWrap: "on", scrollBeyondLastLine: false, padding: { top: 12 } }}
            /> : <div className="usda-empty">
              <Code2 size={24} />
              <strong>{activeQuest?.language === "none" ? "NO LAYER FOR THIS BRIEFING" : "RUN THE ROOM TO AUTHOR USDA"}</strong>
              <p>{activeQuest?.language === "none" ? "This room checks an answer, not a stage." : "The BEFORE tab shows the incoming layer. Your authored result appears here after a run."}</p>
            </div>}
          </div>
          {reviewPending && <button className="continue-button" onClick={continueAfterReview}>
            I SEE THE NEW OPINIONS — CONTINUE <ArrowRight size={15} />
          </button>}
        </section>
      </aside>
    </main>
    {guideStep !== null && pointer && <div className={`guide-pointer ${pointer.side}`} style={{ left: pointer.x, top: pointer.y }} aria-hidden="true">
      <span className="pointer-step">{guideStep + 1}</span>
      <ChevronRight /><ChevronRight />
    </div>}
    {guideStep !== null && <GuideDock
      step={guideStep}
      onBack={() => setGuideStep((current) => Math.max(0, (current ?? 0) - 1))}
      onNext={() => setGuideStep((current) => Math.min(GUIDE_STEPS.length - 1, (current ?? 0) + 1))}
      onClose={closeGuide}
    />}
    {lessonOpen && activeQuest && <div className="lesson-overlay" role="dialog" aria-label={`Lesson for ${activeQuest.title}`}>
      <button className="lesson-backdrop" onClick={() => setLessonOpen(false)} aria-label="Close lesson" />
      <section className={`lesson-drawer ${spotlight === "lesson" ? "spotlight" : ""}`} ref={lessonRef}>
        <header>
          <div><span>LESSON // {activeQuest.lesson?.title || "COOKBOOK"}</span><strong>{activeQuest.title}</strong></div>
          <div className="lesson-actions">
            <a href={cookbookUrl(activeQuest.cookbook)} target="_blank" rel="noreferrer">FULL PAGE <ArrowRight size={13} /></a>
            <button onClick={() => setLessonOpen(false)} aria-label="Close lesson"><X /></button>
          </div>
        </header>
        <div className="lesson-content">
          {activeQuest.lesson ? <>
            <SystemLine text={activeQuest.lesson.intro} tone="intro" />
            <div className="lesson-objective">
              <BookOpen size={15} />
              <div><span>OBJECTIVE</span><p>{activeQuest.lesson.objective}</p></div>
            </div>
            {activeQuest.home_floor && state.specialization && <div className="lesson-class-lens">
              <span>{state.specialization.toUpperCase()} LENS</span>
              <p>{state.specialization === "Compositor"
                ? "Watch which layer authors each opinion, and which arc makes it win."
                : state.specialization === "Aggregator"
                  ? "Watch the asset interface: what is shared, payloaded, instanced, or kinded."
                  : "Watch units, axes, provenance, and whether the result would pass a validator."}</p>
            </div>}
            {activeQuest.lesson.beats.map((beat, index) => <article className={`lesson-beat ${beat.kind}`} key={`${beat.kind}-${index}`}>
              <header>
                <span className="beat-index">{String(index + 1).padStart(2, "0")}</span>
                <div><span className={`beat-kind ${beat.kind}`}>{beat.kind}</span><h3>{beat.heading}</h3></div>
              </header>
              {beat.system && <SystemLine text={beat.system} tone="aside" />}
              {beat.body?.trim().split(/\n{2,}/).map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              {beat.points && beat.points.length > 0 && <ul>
                {beat.points.map((point) => <li key={point}>{point}</li>)}
              </ul>}
              {beat.code && <pre><code>{beat.code.replace(/\n$/, "")}</code></pre>}
            </article>)}
            <section className="lesson-apply">
              <span className="apply-tag">YOUR TASK IN THIS ROOM</span>
              <SystemLine text={activeQuest.lesson.apply} tone="apply" />
            </section>
            <button className="lesson-ack" onClick={acknowledgeLesson}>
              BACK TO THE TERMINAL <ArrowRight size={16} />
            </button>
            <div className="lesson-source">Compressed from the official Learn OpenUSD lesson · {activeQuest.lesson.source}</div>
          </> : <div className="lesson-missing">
            <strong>BRIEFING SIGNAL MISSING</strong>
            <p>Use the full Cookbook page for this room.</p>
          </div>}
        </div>
      </section>
    </div>}
    {toast && <div className={`system-toast ${toast.kind}`}><div className="toast-tag">SYSTEM // {toast.kind === "error" ? "ALERT" : "ANNOUNCEMENT"}</div><button onClick={() => setToast(null)} aria-label="Close notification"><X /></button><strong>{toast.title}</strong><p>{toast.message}</p><div className="toast-scan" /></div>}
  </div>;
}
