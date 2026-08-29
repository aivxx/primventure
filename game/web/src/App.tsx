import { useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  ArrowRight, Backpack, Boxes, BookOpen, ChevronRight, CircleDollarSign, Code2,
  FlaskConical, Gem, HelpCircle, LockKeyhole, Play, RefreshCw, Shield,
  ShoppingCart, Skull, Sparkles, Swords, TerminalSquare, Trophy, X, Zap,
} from "lucide-react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type Language = "python" | "usda" | "none";
type Question = { prompt: string; choices?: string[]; answer?: number; answer_key?: string };
type Quest = {
  id: string; title: string; floor: number; floor_name: string; neighborhood: string;
  kind: "orientation" | "room" | "neighborhood_boss" | "city_boss" | "floor_boss";
  brief: string; language: Language; starter: string; xp: number; reward?: string | object;
  cookbook: string; unlocked: boolean; completed: boolean; exam_tasks: string[];
  stats: Record<string, number>; questions?: Question[];
};
type ShopItem = { name: string; description: string; cost: number; repeatable?: boolean };
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
};
type Toast = { kind: "success" | "error" | "info"; title: string; message: string };

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

type GuideTarget = "challenge" | "editor" | "run" | "map";
const GUIDE_STEPS: Array<{ target: GuideTarget; title: string; body: string }> = [
  {
    target: "challenge",
    title: "Read the room",
    body: "Every room gives you one small authoring job. The brief says what to build. Open Cookbook for the lesson behind it.",
  },
  {
    target: "editor",
    title: "Write the code",
    body: "The terminal holds real Python. A comment marks the line you need to write. STAGE_PATH is already defined for you.",
  },
  {
    target: "run",
    title: "Run the room",
    body: "usd-core opens your stage and checks it. If something is missing, the System tells you which check failed. Nothing is lost when you miss.",
  },
  {
    target: "map",
    title: "Move through the floors",
    body: "Clearing a room unlocks the next one. Each floor ends in a boss, and your cleared work stacks up as a real USD city in world/.",
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

function cookbookUrl(path: string) {
  const relative = path.replace(/^docs\//, "").replace(/\.md$/, ".html");
  return `http://127.0.0.1:8000/cookbook/${relative}`;
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

function ScenePreview({ revision }: { revision: number }) {
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

  return <section className="preview-card panel">
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
  const [revision, setRevision] = useState(0);
  const [toast, setToast] = useState<Toast | null>(null);
  const [showLanding, setShowLanding] = useState(() => localStorage.getItem(ONBOARDED_KEY) !== "1");
  const [guideStep, setGuideStep] = useState<number | null>(null);
  const [mapScope, setMapScope] = useState<"floor" | "all">("floor");
  const booted = useRef(false);

  const refresh = async (advance = false) => {
    const [nextState, nextQuests, nextRecipes] = await Promise.all([
      api<PlayerState>("/state"), api<Quest[]>("/quests"), api<Recipe[]>("/recipes"),
    ]);
    setState(nextState);
    setQuests(nextQuests);
    setRecipes(nextRecipes);
    setActiveQuest((current) => {
      const nextOpen = nextQuests.find((quest) => quest.unlocked && !quest.completed);
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
  }, [activeQuest?.id]);
  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

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
  const focusFloor = activeQuest?.floor ?? nextQuest?.floor ?? 0;
  const visibleFloors = mapScope === "all" ? floors : floors.filter(([floor]) => floor === focusFloor);
  const focusRooms = floors.find(([floor]) => floor === focusFloor)?.[1] || [];
  const focusCleared = focusRooms.filter((quest) => quest.completed).length;
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
      setToast({
        kind: result.success ? "success" : "error",
        title: result.success ? "ROOM CLEARED" : "VALIDATION FAILED",
        message: `${result.system_message} ${result.results.filter((item) => !item.passed).map((item) => item.message).join(" ")}`,
      });
      await refresh(result.success);
      if (result.success) setRevision((value) => value + 1);
    } catch (error) {
      setToast({ kind: "error", title: "SIGNAL LOST", message: error instanceof Error ? error.message : "The API did not answer." });
    } finally {
      setRunning(false);
    }
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
      setState(await api<PlayerState>(`/shop/${id}`, { method: "POST" }));
      setToast({ kind: "success", title: "UPGRADE INSTALLED", message: "No refunds after the screaming starts." });
    } catch (error) {
      setToast({ kind: "error", title: "PURCHASE DENIED", message: error instanceof Error ? error.message : "The kiosk ate your points." });
    }
  };

  const inventory = Object.entries(state.inventory);
  const status = activeQuest ? questStatus(activeQuest) : "locked";

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
        <section className="player-card panel">
          <div className="panel-heading"><span><Swords size={15} /> RUN STATUS</span><em>{state.completed_quests.length}/{quests.length}</em></div>
          <div className="stat-line"><span><Trophy size={15} /> CITY CONTROL</span><b>{quests.length ? Math.round(state.completed_quests.length / quests.length * 100) : 0}%</b></div>
          <div className="meter health"><i style={{ width: `${quests.length ? state.completed_quests.length / quests.length * 100 : 0}%` }} /></div>
          <div className="stat-line"><span><Zap size={15} /> EXPERIENCE</span><b>{state.xp}/{state.next_level_xp}</b></div>
          <div className="meter xp"><i style={{ width: `${xpProgress}%` }} /></div>
          <div className="currency"><CircleDollarSign size={18} /><div><small>OPINION POINTS</small><b>{state.opinion_points}</b></div></div>
          {(state.specialization || state.level >= 2) && <div className="stat-line"><span><Shield size={15} /> CLASS PATH</span><b>{state.specialization || "UNDECLARED"}</b></div>}
        </section>
        {inventory.length > 0 && <section className="inventory panel">
          <div className="panel-heading"><span><Backpack size={15} /> LOADOUT</span><em>{inventory.length}</em></div>
          {inventory.map(([name, quantity]) => <div className="inventory-item" key={name}>
            <span className="item-icon rare"><FlaskConical size={17} /></span><div><strong>{name.replaceAll("_", " ")}</strong><small>System-issued gear</small></div><b>×{quantity}</b>
          </div>)}
        </section>}
        <ScenePreview revision={revision} />
      </aside>
      <section className={`command-center ${spotlight === "map" ? "spotlight" : ""}`}>
        <nav className="mode-tabs">
          <button className={activeTab === "map" ? "active" : ""} onClick={() => setActiveTab("map")}><Skull size={16} /> DUNGEON MAP</button>
          <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}><Sparkles size={16} /> RECIPE TREE</button>
          <button className={activeTab === "kiosk" ? "active" : ""} onClick={() => setActiveTab("kiosk")}><ShoppingCart size={16} /> SAFEROOM</button>
        </nav>
        {activeTab === "map" && <div className="map panel">
          <div className="map-title">
            <div>
              <span>{mapScope === "floor" ? `FLOOR ${String(focusFloor).padStart(2, "0")} · ${focusCleared}/${focusRooms.length} CLEARED` : "CONTESTANT PATH // FLOORS 00–09"}</span>
              <h1>{mapScope === "floor" ? focusRooms[0]?.floor_name || "RECAPTURE PROTOCOL" : "RECAPTURE PROTOCOL"}</h1>
              <p>{nextQuest ? <>Next room: <b>{nextQuest.title}</b>. Click a room to load it into the terminal.</> : "Every room on this route is cleared."}</p>
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
                <button className={`room ${roomStatus} ${activeQuest?.id === quest.id ? "selected" : ""}`} disabled={roomStatus === "locked"} onClick={() => setActiveQuest(quest)}>
                  {roomStatus === "locked" ? <LockKeyhole /> : roomStatus === "boss" ? <Skull /> : roomStatus === "complete" ? <Trophy /> : <Code2 />}
                  <span>{quest.kind.endsWith("boss") ? "BOSS" : `0${index + 1}`}</span>
                </button><small>{quest.title}</small>
              </div>;
            })}</div>
          </div>)}</div>
          <div className="legend"><span><i className="complete" /> CLEARED</span><span><i className="available" /> OPEN</span><span><i className="boss" /> BOSS</span><span><i className="locked" /> LOCKED</span></div>
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
          <div className="section-hero"><span>SAFEROOM KIOSK // OPINIONS FINAL</span><h1>SPEND TO SURVIVE</h1><p>SYSTEM: {state.specialization ? `${state.specialization} still pays rent in Opinion Points.` : "Pick a class path after level 2. The dungeon does not get easier. The flavor does."} Upgrades never clear rooms for you.</p></div>
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
          <div className="shop-grid">{Object.entries(state.shop).map(([id, item], index) => {
            const owned = state.upgrades.includes(id) && !item.repeatable;
            return <article className={owned ? "owned" : ""} key={id}><div className="shop-number">0{index + 1}</div><Shield size={34} /><h3>{item.name}</h3><p>{item.description}</p>
              <button disabled={owned || state.opinion_points < item.cost} onClick={() => buyUpgrade(id)}>{owned ? "INSTALLED" : <><CircleDollarSign size={15} /> {item.cost} OP</>}</button>
            </article>;
          })}</div><small className="fine-print">*Saferoom status void during syntax errors and certification deadlines.</small>
        </div>}
      </section>
      <aside className="editor-rail">
        <section className={`challenge-card ${spotlight === "challenge" ? "spotlight" : ""}`}>
          <div className="eyebrow"><span>{activeQuest?.kind.replaceAll("_", " ").toUpperCase() || "NO SIGNAL"}</span><b>+{activeQuest?.xp || 0} XP</b></div>
          <h2>{activeQuest?.title || "Waiting for the System"}</h2><p>{activeQuest?.brief}</p>
          <div className="objective"><ChevronRight size={16} /><span><small>NEIGHBORHOOD</small>{activeQuest?.neighborhood}</span></div>
          {activeQuest && <a className="cookbook-link" href={cookbookUrl(activeQuest.cookbook)} target="_blank" rel="noreferrer"><BookOpen size={15} /> OPEN COOKBOOK</a>}
          {activeQuest?.questions?.map((question, index) => <label className="boss-question" key={question.prompt}>{question.prompt}
            {question.choices?.length ? <select value={String(answers[index] ?? "")} onChange={(event) => setAnswers((current) => current.map((answer, i) => i === index ? Number(event.target.value) : answer))}>
              <option value="">Choose…</option>{question.choices.map((choice, choiceIndex) => <option value={choiceIndex} key={choice}>{choice}</option>)}
            </select> : <input value={String(answers[index] ?? "")} onChange={(event) => setAnswers((current) => current.map((answer, i) => i === index ? event.target.value : answer))} placeholder="Explain your reasoning…" />}
          </label>)}
        </section>
        <section className={`code-panel panel ${spotlight === "editor" ? "spotlight" : ""}`}>
          <div className="editor-toolbar"><span><TerminalSquare size={15} /> ROOM TERMINAL</span><div><button className="active">{activeQuest?.language.toUpperCase() || "—"}</button></div></div>
          <Editor height="100%" language={activeQuest?.language === "python" ? "python" : "plaintext"} theme="vs-dark" value={code} onChange={(value) => setCode(value || "")} options={{ readOnly: activeQuest?.language === "none", minimap: { enabled: false }, fontSize: 13, lineHeight: 21, padding: { top: 16 }, scrollBeyondLastLine: false, tabSize: 4 }} />
        </section>
        <button className={`run-button ${spotlight === "run" ? "spotlight" : ""}`} onClick={runQuest} disabled={running || !activeQuest || status === "locked"}>
          {running ? <RefreshCw className="spin" /> : <Play fill="currentColor" />} {running ? "JUDGES ARE THINKING..." : activeQuest?.language === "none" ? "ACKNOWLEDGE BRIEF" : "RUN THE ROOM"}
        </button>
      </aside>
    </main>
    {guideStep !== null && <GuideDock
      step={guideStep}
      onBack={() => setGuideStep((current) => Math.max(0, (current ?? 0) - 1))}
      onNext={() => setGuideStep((current) => Math.min(GUIDE_STEPS.length - 1, (current ?? 0) + 1))}
      onClose={closeGuide}
    />}
    {toast && <div className={`system-toast ${toast.kind}`}><div className="toast-tag">SYSTEM // {toast.kind === "error" ? "ALERT" : "ANNOUNCEMENT"}</div><button onClick={() => setToast(null)} aria-label="Close notification"><X /></button><strong>{toast.title}</strong><p>{toast.message}</p><div className="toast-scan" /></div>}
  </div>;
}
