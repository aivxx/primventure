import { useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  ArrowRight, Backpack, Boxes, BookOpen, CheckCircle2, ChevronRight, Circle,
  CircleDollarSign, Code2, Eye, FlaskConical, Gem, HelpCircle, Lightbulb,
  ListChecks, LockKeyhole, Play, RefreshCw, Shield, ShoppingCart, Skull,
  Sparkles, Swords, TerminalSquare, Trophy, X, XCircle, Zap,
} from "lucide-react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

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
  opinion_points: number; expects: string[];
};
type ShopItem = {
  name: string; description: string; cost: number; repeatable?: boolean;
  kind?: "consumable" | "upgrade";
};
type PlayerState = {
  contestant: string; title: string; level: number; xp: number; next_level_xp: number;
  opinion_points: number; completed_quests: string[]; stats: Record<string, number>;
  inventory: Record<string, number>; upgrades: string[]; recipes: string[];
  achievements: string[]; specialization?: string; shop: Record<string, ShopItem>;
};
type Recipe = { id: string; label: string; category: string; unlocked: boolean };
type RunResult = {
  success: boolean; output: string; system_message: string;
  results: Array<{ rule: string; passed: boolean; message: string }>; state: PlayerState;
  before_usda: string; after_usda: string;
};
type USDAView = { before_usda: string; after_usda: string };
type Toast = { kind: "success" | "error" | "info"; title: string; message: string };
type AssistResult = { kind: "hint" | "peek"; title: string; message: string };
type HintResponse = { hint: string; state: PlayerState };
type PeekResponse = {
  peek: { layer: string; sublayers: string[]; message: string };
  state: PlayerState;
};

const CLASS_PATHS = [
  {
    id: "Compositor",
    title: "Compositor",
    blurb: "You argue in LIVERPS. Layers, arcs, and opinions are your weapons.",
  },
  {
    id: "Aggregator",
    title: "Aggregator",
    blurb: "You assemble the city. Payloads, kinds, and workstreams stay inspectable.",
  },
  {
    id: "Exchanger",
    title: "Exchanger",
    blurb: "You translate the outside world. Units, checkers, and honest extracts.",
  },
] as const;

const ONBOARDED_KEY = "primventure.onboarded.v2";
const GUIDED_KEY = "primventure.guided";
const LESSONS_READ_KEY = "primventure.lessons-read.v1";
const USDA_REVIEW_KEY = "primventure.usda-review";

type GuideTarget = "lesson" | "editor" | "run" | "usda" | "map" | "payout" | "consumables" | "feed";
// Panels on the left edge have no room for an arrow beside them, and the
// tutorial card owns the bottom left, so those targets get pointed at from the
// right instead of being covered by their own callout.
const POINTER_SIDE: Record<GuideTarget, "left" | "right"> = {
  lesson: "right",
  editor: "right",
  run: "left",
  usda: "right",
  map: "right",
  payout: "left",
  consumables: "left",
  feed: "left",
};
const GUIDE_STEPS: Array<{ target: GuideTarget; title: string; body: string }> = [
  {
    target: "lesson",
    title: "Learn this room",
    body: "The System introduces the official lesson, then hands you the concepts, API calls, and traps this room needs. Read the beats, then acknowledge the briefing.",
  },
  {
    target: "editor",
    title: "Write the code",
    body: "This is the terminal. It holds real Python, with a blank line under each instruction to write on. STAGE_PATH and the closing Save() are already supplied.",
  },
  {
    target: "run",
    title: "Run the room",
    body: "usd-core opens your stage and checks it against the list in the room card. Nothing is lost when a check fails, so run as often as you need to.",
  },
  {
    target: "usda",
    title: "Read the USDA you authored",
    body: "This panel holds the layer itself. BEFORE is the stage the room handed you, AFTER is what your code wrote, and the first changed line is highlighted.",
  },
  {
    target: "map",
    title: "Move through the floors",
    body: "Clear the rooms to learn the floor. The boss is the exit exam, and your cleared work stacks up as a real USD city in world/. Rooms tagged +OP on the map pay Opinion Points the first time you clear them.",
  },
  {
    target: "payout",
    title: "Get paid in Opinion Points",
    body: "Opinion Points are the only currency, and boss rooms are what pay them. This counter holds your balance and names the next room that will top it up.",
  },
  {
    target: "consumables",
    title: "Spend it on consumables",
    body: "Hint Tokens buy you a clue for the room you are stuck on. Opinion X-Rays show the composed layer stack after you clear a room. Click one here to use it, and hit SAFEROOM to buy more once a boss has paid you.",
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

const TICKER = [
  "A NEW CONTESTANT HAS ENTERED THE COMPOSITION",
  "THE BROADCAST IS LIVE IN EVERY REMAINING TIMEZONE",
  "NO EXPERIENCE REQUIRED · NONE DETECTED EITHER",
  "TEN FLOORS REMAIN SEALED · NINE OF THEM ARE NOT YOUR PROBLEM YET",
  "THE PREVIOUS CONTESTANT DECLINED TO READ THE BRIEF",
  "SPONSORS REMIND YOU THAT PANIC IS NOT A STRATEGY",
  "NOTHING HERE IS PERMANENT EXCEPT THE CITY YOU BUILD",
];

const SPONSORS = [
  "THIS SEGMENT IS BROUGHT TO YOU BY THE ESTATE OF THE FOURTH FLOOR",
  "SPONSOR: A FIRM THAT NO LONGER RESOLVES · TERMS UNAVAILABLE",
  "VIEWER DISCRETION IS ADVISED · THE SYSTEM'S IS NOT",
  "STANDINGS UPDATE HOURLY · YOURS IS NOT ON THE BOARD",
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
  return <div className="landing">
    <BroadcastChrome />
    <div className="landing-ticker">
      <span className="ticker-live"><span className="live-dot" /> LIVE</span>
      <div className="ticker-window">
        <div className="ticker-track">
          {[...TICKER, ...TICKER].map((line, index) => <em key={index}>SYSTEM // {line}</em>)}
        </div>
      </div>
      <span className="ticker-clock">SEASON 01 · EP 00</span>
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
          <span>PRIMWRIGHT · UNDERQUALIFIED · AWAITING FLOOR 00</span>
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
          scene what it is. Do not be flattered. I did not interview you. I skimmed one line of your work history,
          laughed, and printed a badge. It reads <em>Contestant #USD-01</em>. <em>Primwright</em>.
          <em> Underqualified</em>. I ran out of room before I ran out of adjectives.
        </p>
        <p>
          House rules, which you will ignore in roughly four minutes. I assign the work. I do not grade it — real
          tooling does, so when you fail you are failing to an impartial third party and to me, personally, out loud.
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
          Win and your work is filed into a real 3D city that keeps growing on your disk. Miss and the System says
          something unkind and hands the room straight back. Nothing you build is ever taken away — the worst outcome
          here is being talked about.
        </p>
      </section>

      <section className="landing-tower">
        <h2>THE TOWER · TEN FLOORS, NO ELEVATOR</h2>
        <p className="landing-note">
          Cleared in order. Every floor teaches a new part of OpenUSD and ends with something that declines to let you
          pass politely. The System does not post what that something is. The System finds this funnier.
        </p>
        <div className="tower-grid">
          {floors.map(([floor, rooms]) => {
            const bosses = rooms.filter((room) => room.kind.endsWith("boss")).length;
            return <div className={`tower-floor ${floor === 0 ? "open" : ""}`} key={floor}>
              <span className="tower-index">{String(floor).padStart(2, "0")}</span>
              <div>
                <strong>{rooms[0]?.floor_name}</strong>
                <small>{rooms.length} rooms · {bosses} guarded</small>
              </div>
              {floor === 0 ? <em className="tower-open">OPEN</em> : <LockKeyhole size={13} />}
            </div>;
          })}
        </div>
      </section>

      <div className="landing-launch">
        <button className="landing-cta" onClick={onStart} autoFocus>
          {hasProgress ? "CONTINUE RUN" : "ENTER THE COMPOSITION"} <ArrowRight size={18} />
        </button>
        <p className="landing-next">
          {nextQuest
            ? <>Floor 00 · your first assignment: <b>{nextQuest.title}</b></>
            : "Connecting to the local arena…"}
        </p>
        <small className="landing-fine">
          No OpenUSD experience required · a walkthrough holds your hand through room one · runs entirely on your own
          machine, where the audience is theoretical
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
    setStatus("PROCEDURAL STAND-IN");
    new GLTFLoader().load(`/api/world/preview?rev=${revision}`, (gltf) => {
      if (disposed) return;
      scene.remove(fallback);
      model = gltf.scene;
      const box = new THREE.Box3().setFromObject(model);
      model.scale.multiplyScalar(2.4 / (box.getSize(new THREE.Vector3()).length() || 1));
      model.position.sub(new THREE.Box3().setFromObject(model).getCenter(new THREE.Vector3()));
      scene.add(model);
      setStatus("LIVE GLTF FEED");
    }, undefined, () => setStatus("USD STAGE ONLINE"));
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
    <div className="preview-meta"><span>STAGE: world/root.usda</span><span>UP: Y</span><span>24 FPS</span></div>
  </section>;
}

export default function App() {
  const [state, setState] = useState<PlayerState>(emptyState);
  const [quests, setQuests] = useState<Quest[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [activeQuest, setActiveQuest] = useState<Quest | null>(null);
  const [code, setCode] = useState("");
  const [answers, setAnswers] = useState<Array<number | string>>([]);
  const [activeTab, setActiveTab] = useState<"map" | "skills" | "kiosk">("map");
  const [running, setRunning] = useState(false);
  const [assistBusy, setAssistBusy] = useState<"hint" | "peek" | null>(null);
  const [assistResult, setAssistResult] = useState<AssistResult | null>(null);
  const [pendingSpend, setPendingSpend] = useState<"hint_tokens" | "system_peeks" | null>(null);
  const [checks, setChecks] = useState<boolean[]>([]);
  const [usdaView, setUsdaView] = useState<USDAView>({ before_usda: "", after_usda: "" });
  const [usdaMode, setUsdaMode] = useState<"before" | "after">("before");
  const [reviewPending, setReviewPending] = useState(false);
  const [revision, setRevision] = useState(0);
  const [toast, setToast] = useState<Toast | null>(null);
  const [showLanding, setShowLanding] = useState(() => localStorage.getItem(ONBOARDED_KEY) !== "1");
  const [guideStep, setGuideStep] = useState<number | null>(null);
  const [mapScope, setMapScope] = useState<"floor" | "all">("floor");
  const [pointer, setPointer] = useState<{ x: number; y: number; side: "left" | "right" } | null>(null);
  const [lessonOpen, setLessonOpen] = useState(false);
  const [, setLessonRevision] = useState(0);
  const booted = useRef(false);
  const lessonRef = useRef<HTMLElement>(null);
  const editorRef = useRef<HTMLElement>(null);
  const focusEditor = useRef<(() => void) | null>(null);
  const runRef = useRef<HTMLButtonElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const usdaRef = useRef<HTMLElement>(null);
  const payoutRef = useRef<HTMLElement>(null);
  const consumablesRef = useRef<HTMLElement>(null);
  const feedRef = useRef<HTMLElement>(null);

  const refresh = async (advance = false) => {
    const [nextState, nextQuests, nextRecipes] = await Promise.all([
      api<PlayerState>("/state"), api<Quest[]>("/quests"), api<Recipe[]>("/recipes"),
    ]);
    setState(nextState);
    setQuests(nextQuests);
    setRecipes(nextRecipes);
    setActiveQuest((current) => {
      const nextOpen = nextQuests.find((quest) => quest.unlocked && !quest.completed);
      const reviewId = localStorage.getItem(USDA_REVIEW_KEY);
      const reviewQuest = reviewId ? nextQuests.find((quest) => quest.id === reviewId) : null;
      if (!advance && reviewQuest) return reviewQuest;
      if (advance && nextOpen) return nextOpen;
      if (current) return nextQuests.find((quest) => quest.id === current.id) || current;
      return nextOpen || nextQuests[0] || null;
    });
    // Only skip the intro automatically on the first load of a run in progress.
    // Reopening it from the wordmark should stick until the player dismisses it.
    if (!booted.current) {
      booted.current = true;
      if (nextState.completed_quests.length > 0) {
        localStorage.setItem(ONBOARDED_KEY, "1");
        localStorage.setItem(GUIDED_KEY, "1");
        setShowLanding(false);
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
    setActiveQuest(quest);
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
    if (!activeQuest) return;
    setCode(activeQuest.starter || "");
    setAnswers(activeQuest.questions?.map(() => "") || []);
    setAssistResult(null);
    setPendingSpend(null);
    setChecks([]);
    const owesReview = localStorage.getItem(USDA_REVIEW_KEY) === activeQuest.id;
    setReviewPending(owesReview);
    setUsdaMode(activeQuest.completed || owesReview ? "after" : "before");
  }, [activeQuest?.id]);
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
    if (target === "map") setActiveTab("map");
    // The drawer covers the screen, so it has to step aside once the tour
    // moves on to the terminal behind it.
    setLessonOpen(target === "lesson");
  }, [guideStep]);

  // Park the arrow just outside the left edge of whatever the tutorial is
  // describing, so the callout and the outline agree on the target.
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
      payout: payoutRef.current,
      consumables: consumablesRef.current,
      feed: feedRef.current,
    } as Record<GuideTarget, HTMLElement | null>)[target];
    const measure = () => {
      const rect = node()?.getBoundingClientRect();
      if (!rect || !rect.width) {
        setPointer(null);
        return;
      }
      const side = POINTER_SIDE[target];
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
  const focusFloor = activeQuest?.floor ?? nextQuest?.floor ?? 0;
  const visibleFloors = mapScope === "all" ? floors : floors.filter(([floor]) => floor === focusFloor);
  const focusRooms = floors.find(([floor]) => floor === focusFloor)?.[1] || [];
  const focusCleared = focusRooms.filter((quest) => quest.completed).length;
  const lessonRead = activeQuest ? lessonsRead().has(activeQuest.id) : false;
  const spotlight = guideStep === null ? null : GUIDE_STEPS[guideStep].target;
  const xpFloor = (state.level - 1) * 100;
  const xpProgress = ((state.xp - xpFloor) / Math.max(state.next_level_xp - xpFloor, 1)) * 100;

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
      if (needsUsdaReview) {
        setToast(null);
        localStorage.setItem(USDA_REVIEW_KEY, activeQuest.id);
        setReviewPending(true);
        setRevision((value) => value + 1);
        window.setTimeout(() => usdaRef.current?.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
      } else if (!result.success) {
        setToast({
          kind: "error",
          title: "VALIDATION FAILED",
          message: `${!lessonRead ? "SYSTEM: You skipped the briefing. The lesson remains available. " : ""}${result.system_message} ${result.results.filter((item) => !item.passed).map((item) => item.message).join(" ")}`,
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

  const useSystemPeek = async () => {
    if (!activeQuest || assistBusy) return;
    setAssistBusy("peek");
    try {
      const result = await api<PeekResponse>(`/quests/${activeQuest.id}/peek`, { method: "POST" });
      setState(result.state);
      const sublayers = result.peek.sublayers.length
        ? ` Sublayers, strongest first: ${result.peek.sublayers.join(", ")}.`
        : " No sublayers are authored.";
      setAssistResult({
        kind: "peek",
        title: "OPINION X-RAY",
        message: `${result.peek.message} Layer: ${result.peek.layer}.${sublayers}`,
      });
    } catch (error) {
      setToast({
        kind: "error",
        title: "PEEK DENIED",
        message: error instanceof Error ? error.message : "The layer stack remained opaque.",
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
        message: `SYSTEM: ${id} recorded. You may still clear every floor. Flavor is not a cheat.`,
      });
    } catch (error) {
      setToast({ kind: "error", title: "PATH DENIED", message: error instanceof Error ? error.message : "The kiosk refused." });
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

  const inventory = Object.entries(state.inventory);
  const hintTokens = state.inventory.hint_tokens || 0;
  const systemPeeks = state.inventory.system_peeks || 0;
  const consumables = [
    { id: "hint_tokens" as const, quantity: hintTokens, cost: state.shop?.hint_refill?.cost },
    { id: "system_peeks" as const, quantity: systemPeeks, cost: state.shop?.system_peek?.cost },
  ];
  const keyItems = inventory.filter(([name]) => name !== "hint_tokens" && name !== "system_peeks");
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
        <div><strong>PRIMVENTURE</strong><small>THE COMPOSITION IS LIVE</small></div>
      </button>
      <div className="broadcast"><span className="live-dot" /> LOCAL ARENA <b>USD-CORE</b></div>
      <div className="player-strip">
        <button className="help-button" onClick={() => setGuideStep(0)}><HelpCircle size={14} /> HOW TO PLAY</button>
        <div className="avatar">{state.contestant.slice(-2)}</div><div><small>{state.title}</small><strong>{state.contestant}</strong></div><span className="level">LVL {state.level}</span>
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
          <div className="currency"><CircleDollarSign size={18} /><div><small>OPINION POINTS</small><b>{state.opinion_points}</b></div></div>
          <p className="currency-note">
            Earned by clearing boss rooms. {nextPayingQuest
              ? <>Next payout: <b>{nextPayingQuest.title}</b> (+{nextPayingQuest.opinion_points} OP).</>
              : "Every paying room on this route is cleared."}
          </p>
          {(state.specialization || state.level >= 2) && <div className="stat-line"><span><Shield size={15} /> CLASS PATH</span><b>{state.specialization || "UNDECLARED"}</b></div>}
        </section>
        <section className={`inventory panel ${spotlight === "consumables" ? "spotlight" : ""}`} ref={consumablesRef}>
          <div className="panel-heading"><span><FlaskConical size={15} /> CONSUMABLES</span><button className="restock-link" onClick={() => setActiveTab("kiosk")}>SAFEROOM</button></div>
          {consumables.map(({ id, quantity, cost }) => {
            const isHint = id === "hint_tokens";
            const unavailable = quantity < 1 || assistBusy !== null || (!isHint && !activeQuest?.completed);
            const label = isHint ? "Hint Token" : "Opinion X-Ray";
            const detail = quantity < 1
              ? `Out of stock · ${cost ?? "?"} OP in Saferoom`
              : isHint
                ? "Tap to use · room-level clue"
                : activeQuest?.completed ? "Tap to use · reads the published layer" : "Clear this room to use";
            const icon = (isHint && assistBusy === "hint") || (!isHint && assistBusy === "peek")
              ? <RefreshCw className="spin" />
              : isHint ? <Lightbulb size={17} /> : <Eye size={17} />;
            // Spending is irreversible, so the first click only arms the item.
            if (pendingSpend === id) {
              return <div className="inventory-item confirming" key={id}>
                <span className={`item-icon ${isHint ? "rare" : "epic"}`}>{icon}</span>
                <div><strong>Spend 1 {isHint ? "Hint" : "X-Ray"}?</strong><small>{quantity - 1} would be left</small></div>
                <div className="confirm-actions">
                  <button className="yes" onClick={() => { setPendingSpend(null); (isHint ? useHint : useSystemPeek)(); }}>SPEND</button>
                  <button className="no" onClick={() => setPendingSpend(null)} aria-label={`Keep the ${label}`}><X size={13} /></button>
                </div>
              </div>;
            }
            return <button
              className="inventory-item usable"
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
            <p>{assistResult.message}</p>
          </div>}
        </section>
        {keyItems.length > 0 && <section className="inventory panel key-items">
          <div className="panel-heading"><span><Backpack size={15} /> KEY ITEMS</span><em>{keyItems.length}</em></div>
          {keyItems.map(([name, quantity]) => <div className="inventory-item passive" key={name}>
            <span className="item-icon legendary"><Backpack size={17} /></span>
            <div><strong>{name.replaceAll("_", " ")}</strong><small>Room-clear trophy</small></div>
            <b>× {quantity}</b>
          </div>)}
        </section>}
        <ScenePreview revision={revision} panelRef={feedRef} spotlit={spotlight === "feed"} />
      </aside>
      <section className="command-center">
        <nav className="mode-tabs">
          <button className={activeTab === "map" ? "active" : ""} onClick={() => setActiveTab("map")}><Skull size={16} /> DUNGEON MAP</button>
          <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}><Sparkles size={16} /> RECIPE TREE</button>
          <button className={activeTab === "kiosk" ? "active" : ""} onClick={() => setActiveTab("kiosk")}><ShoppingCart size={16} /> SAFEROOM</button>
        </nav>
        {activeTab === "map" && <div className={`map panel ${spotlight === "map" ? "spotlight" : ""}`} ref={mapRef}>
          <div className="map-title">
            <div>
              <span>{mapScope === "floor" ? `FLOOR ${String(focusFloor).padStart(2, "0")} · ${focusCleared}/${focusRooms.length} CLEARED` : "CONTESTANT PATH // FLOORS 00–09"}</span>
              <h1>{mapScope === "floor" ? focusRooms[0]?.floor_name || "RECAPTURE PROTOCOL" : "RECAPTURE PROTOCOL"}</h1>
              <p>{nextQuest ? <>Clear the rooms to learn the floor. The boss is the exit exam, and it pays the Opinion Points you spend on consumables. Next: <b>{nextQuest.title}</b>.</> : "Every room on this route is cleared."}</p>
              <div className="map-scope">
                <button className={mapScope === "floor" ? "active" : ""} onClick={() => setMapScope("floor")}>THIS FLOOR</button>
                <button className={mapScope === "all" ? "active" : ""} onClick={() => setMapScope("all")}>ALL FLOORS</button>
              </div>
            </div>
            <div className="completion"><b>{state.completed_quests.length}/{quests.length}</b><small>ROOMS CLEARED</small></div>
          </div>
          <div className="floor-list">{visibleFloors.map(([floor, rooms]) => <div className="floor" key={floor}>
            <div className="floor-label"><span>FLOOR {String(floor).padStart(2, "0")}</span><strong>{rooms[0]?.floor_name}</strong></div>
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
          <div className="legend"><span><i className="complete" /> CLEARED</span><span><i className="available" /> OPEN</span><span><i className="boss" /> BOSS</span><span><i className="locked" /> LOCKED</span><span>+OP PAYS OPINION POINTS FOR THE SAFEROOM</span></div>
        </div>}
        {activeTab === "skills" && <div className="skill-tree panel">
          <div className="section-hero"><span>THE COOKBOOK INDEX</span><h1>RECIPES OF POWER</h1><p>Glossary nodes from the Cookbook graph. Clear rooms that name them. SYSTEM: collecting terms is not the same as composing them.</p><small className="recipe-count">{masteredRecipes}/{recipes.length} MASTERED</small></div>
          {recipeGroups.map(([category, nodes]) => <section className="recipe-cluster" key={category}>
            <header><span>{category.replaceAll("-", " ")}</span><b>{nodes.filter((node) => node.unlocked).length}/{nodes.length}</b></header>
            <div className="skill-grid">{nodes.map((recipe, index) => <article className={`skill-node ${recipe.unlocked ? "unlocked" : ""}`} key={recipe.id} style={{ "--i": index } as React.CSSProperties}>
              <span className="skill-gem">{recipe.unlocked ? <Gem /> : <LockKeyhole />}</span><small>{recipe.category.replaceAll("-", " ")}</small><h3>{recipe.label}</h3><p>{recipe.unlocked ? "Authored in a cleared room. Keep the composed result inspectable." : "Undiscovered. Win a room that names this term."}</p><footer>{recipe.unlocked ? "MASTERED" : "UNDISCOVERED"}</footer>
            </article>)}</div>
          </section>)}
        </div>}
        {activeTab === "kiosk" && <div className="kiosk panel">
          <div className="section-hero"><span>SAFEROOM KIOSK // OPINIONS FINAL</span><h1>SPEND TO SURVIVE</h1><p>SYSTEM: Everything here costs Opinion Points, and Opinion Points come from clearing boss rooms. {nextPayingQuest ? `Your next payout is ${nextPayingQuest.title}, worth ${nextPayingQuest.opinion_points}.` : "You have cleared every paying room on this route."} Consumables land in the left rail. Upgrades never clear rooms for you.</p><small className="recipe-count">{state.opinion_points} OP BANKED</small></div>
          <div className="class-grid">{CLASS_PATHS.map((path) => {
            const selected = state.specialization === path.id;
            const lockedOut = Boolean(state.specialization) && !selected;
            const tooSoon = state.level < 2;
            return <article className={selected ? "owned" : ""} key={path.id}>
              <Shield size={34} /><h3>{path.title}</h3><p>{path.blurb}</p>
              <button disabled={selected || lockedOut || tooSoon} onClick={() => chooseClass(path.id)}>
                {selected ? "DECLARED" : tooSoon ? "LEVEL 2 REQUIRED" : lockedOut ? "PATH CLOSED" : "DECLARE PATH"}
              </button>
            </article>;
          })}</div>
          {shopSections.map((section) => <div className="shop-section" key={section.id}>
            <div className="shop-heading">{section.heading}</div>
            <div className="shop-grid">{section.items.map(([id, item], index) => {
              const owned = state.upgrades.includes(id) && !item.repeatable;
              return <article className={owned ? "owned" : ""} key={id}><div className="shop-number">0{index + 1}</div>{item.kind === "consumable" ? <FlaskConical size={34} /> : <Shield size={34} />}<h3>{item.name}</h3><p>{item.description}</p>
                <button disabled={owned || state.opinion_points < item.cost} onClick={() => buyUpgrade(id)}>{owned ? "INSTALLED" : state.opinion_points < item.cost ? `NEED ${item.cost - state.opinion_points} MORE OP` : item.repeatable ? <><CircleDollarSign size={15} /> {item.cost} OP · RESTOCK</> : <><CircleDollarSign size={15} /> {item.cost} OP</>}</button>
              </article>;
            })}</div>
          </div>)}<small className="fine-print">*Saferoom status void during syntax errors and certification deadlines.</small>
        </div>}
        <section className={`authoring-dock code-panel panel ${spotlight === "editor" ? "spotlight" : ""}`} ref={editorRef}>
          <div className="editor-toolbar">
            <span><TerminalSquare size={15} /> ROOM TERMINAL</span>
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
          <button className={`run-button ${spotlight === "run" ? "spotlight" : ""}`} onClick={runQuest} disabled={running || !activeQuest || status === "locked" || reviewPending} ref={runRef}>
            {running ? <RefreshCw className="spin" /> : reviewPending ? <CheckCircle2 /> : <Play fill="currentColor" />} {running ? "JUDGES ARE THINKING..." : reviewPending ? "ROOM CLEARED — REVIEW USDA →" : activeQuest?.language === "none" ? "ACKNOWLEDGE BRIEF" : "RUN THE ROOM"}
          </button>
        </section>
      </section>
      <aside className="editor-rail">
        <section className="challenge-card">
          <div className="eyebrow"><span>{activeQuest?.kind.replaceAll("_", " ").toUpperCase() || "NO SIGNAL"}</span><b>+{activeQuest?.xp || 0} XP{activeQuest?.opinion_points ? ` · +${activeQuest.opinion_points} OP` : ""}</b></div>
          <h2>{activeQuest?.title || "Waiting for the System"}</h2><p>{activeQuest?.brief}</p>
          <div className="objective"><ChevronRight size={16} /><span><small>NEIGHBORHOOD</small>{activeQuest?.neighborhood}</span></div>
          {activeQuest && <div className="learning-route">
            <span className={lessonRead ? "done" : "current"}><b>1</b> LEARN</span><i />
            <span className={reviewPending ? "done" : lessonRead ? "current" : ""}><b>2</b> AUTHOR</span><i />
            <span className={reviewPending ? "done" : checks.length ? "current" : ""}><b>3</b> VALIDATE</span><i />
            <span className={reviewPending ? "current" : ""}><b>4</b> REVIEW</span>
          </div>}
          {activeQuest && <button className="cookbook-link" onClick={() => setLessonOpen(true)}><BookOpen size={15} /> {lessonRead ? "REVIEW LESSON" : "LEARN THIS ROOM"}</button>}
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
            <span><Code2 size={15} /> AUTHORED USDA</span>
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
    {lessonOpen && activeQuest && <div className="lesson-overlay" role="dialog" aria-modal="true" aria-label={`Lesson for ${activeQuest.title}`}>
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
              <span className="apply-tag">THAT IS THE FIGHT</span>
              <SystemLine text={activeQuest.lesson.apply} tone="apply" />
            </section>
            <button className="lesson-ack" onClick={acknowledgeLesson}>
              {lessonRead ? "BACK TO THE TERMINAL" : "I GOT IT · LET ME AUTHOR"} <ArrowRight size={16} />
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
