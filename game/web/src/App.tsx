import { useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  Backpack, Boxes, BookOpen, ChevronRight, CircleDollarSign, Code2, FlaskConical,
  Gem, LockKeyhole, Play, RefreshCw, Shield, ShoppingCart, Skull, Sparkles,
  Swords, TerminalSquare, Trophy, X, Zap,
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
  const [toast, setToast] = useState<Toast | null>({
    kind: "info", title: "SYSTEM ONLINE",
    message: "Contestant telemetry connected. Try not to author an over where a def should live.",
  });

  const refresh = async () => {
    const [nextState, nextQuests, nextRecipes] = await Promise.all([
      api<PlayerState>("/state"), api<Quest[]>("/quests"), api<Recipe[]>("/recipes"),
    ]);
    setState(nextState);
    setQuests(nextQuests);
    setRecipes(nextRecipes);
    setActiveQuest((current) => {
      if (current) return nextQuests.find((quest) => quest.id === current.id) || current;
      return nextQuests.find((quest) => quest.unlocked && !quest.completed) || nextQuests[0] || null;
    });
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
      await refresh();
      if (result.success) setRevision((value) => value + 1);
    } catch (error) {
      setToast({ kind: "error", title: "SIGNAL LOST", message: error instanceof Error ? error.message : "The API did not answer." });
    } finally {
      setRunning(false);
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
  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><span>P</span></div><div><strong>PRIMVENTURE</strong><small>THE COMPOSITION IS LIVE</small></div></div>
      <div className="broadcast"><span className="live-dot" /> LOCAL ARENA <b>USD-CORE</b></div>
      <div className="player-strip"><div className="avatar">{state.contestant.slice(-2)}</div><div><small>{state.title}</small><strong>{state.contestant}</strong></div><span className="level">LVL {state.level}</span></div>
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
        </section>
        <section className="inventory panel">
          <div className="panel-heading"><span><Backpack size={15} /> LOADOUT</span><em>{inventory.length}</em></div>
          {inventory.map(([name, quantity]) => <div className="inventory-item" key={name}>
            <span className="item-icon rare"><FlaskConical size={17} /></span><div><strong>{name.replaceAll("_", " ")}</strong><small>System-issued gear</small></div><b>×{quantity}</b>
          </div>)}
        </section>
        <ScenePreview revision={revision} />
      </aside>
      <section className="command-center">
        <nav className="mode-tabs">
          <button className={activeTab === "map" ? "active" : ""} onClick={() => setActiveTab("map")}><Skull size={16} /> DUNGEON MAP</button>
          <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}><Sparkles size={16} /> RECIPE TREE</button>
          <button className={activeTab === "kiosk" ? "active" : ""} onClick={() => setActiveTab("kiosk")}><ShoppingCart size={16} /> SAFEROOM</button>
        </nav>
        {activeTab === "map" && <div className="map panel">
          <div className="map-title"><div><span>CONTESTANT PATH // FLOORS 00–09</span><h1>RECAPTURE PROTOCOL</h1><p>Clear every room. Beat the bosses. Keep the layer stack inspectable.</p></div><div className="completion"><b>{state.completed_quests.length}/{quests.length}</b><small>ROOMS CLEARED</small></div></div>
          <div className="floor-list">{floors.map(([floor, rooms]) => <div className="floor" key={floor}>
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
          <div className="section-hero"><span>THE COOKBOOK INDEX</span><h1>RECIPES OF POWER</h1><p>Use glossary concepts in successful fights to unlock them.</p></div>
          <div className="skill-grid">{recipes.map((recipe, index) => <article className={`skill-node ${recipe.unlocked ? "unlocked" : ""}`} key={recipe.id} style={{ "--i": index } as React.CSSProperties}>
            <span className="skill-gem">{recipe.unlocked ? <Gem /> : <LockKeyhole />}</span><small>{recipe.category.replaceAll("-", " ")}</small><h3>{recipe.label}</h3><p>OpenUSD Cookbook recipe</p><footer>{recipe.unlocked ? "MASTERED" : "UNDISCOVERED"}</footer>
          </article>)}</div>
        </div>}
        {activeTab === "kiosk" && <div className="kiosk panel">
          <div className="section-hero"><span>SAFEROOM KIOSK // OPINIONS FINAL</span><h1>SPEND TO SURVIVE</h1><p>Upgrades improve inspection and hints. They never clear rooms for you.</p></div>
          <div className="shop-grid">{Object.entries(state.shop).map(([id, item], index) => {
            const owned = state.upgrades.includes(id) && !item.repeatable;
            return <article className={owned ? "owned" : ""} key={id}><div className="shop-number">0{index + 1}</div><Shield size={34} /><h3>{item.name}</h3><p>{item.description}</p>
              <button disabled={owned || state.opinion_points < item.cost} onClick={() => buyUpgrade(id)}>{owned ? "INSTALLED" : <><CircleDollarSign size={15} /> {item.cost} OP</>}</button>
            </article>;
          })}</div><small className="fine-print">*Saferoom status void during syntax errors and certification deadlines.</small>
        </div>}
      </section>
      <aside className="editor-rail">
        <section className="challenge-card">
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
        <section className="code-panel panel">
          <div className="editor-toolbar"><span><TerminalSquare size={15} /> ROOM TERMINAL</span><div><button className="active">{activeQuest?.language.toUpperCase() || "—"}</button></div></div>
          <Editor height="100%" language={activeQuest?.language === "python" ? "python" : "plaintext"} theme="vs-dark" value={code} onChange={(value) => setCode(value || "")} options={{ readOnly: activeQuest?.language === "none", minimap: { enabled: false }, fontSize: 13, lineHeight: 21, padding: { top: 16 }, scrollBeyondLastLine: false, tabSize: 4 }} />
        </section>
        <button className="run-button" onClick={runQuest} disabled={running || !activeQuest || status === "locked"}>
          {running ? <RefreshCw className="spin" /> : <Play fill="currentColor" />} {running ? "JUDGES ARE THINKING..." : activeQuest?.language === "none" ? "ACKNOWLEDGE BRIEF" : "RUN THE ROOM"}
        </button>
      </aside>
    </main>
    {toast && <div className={`system-toast ${toast.kind}`}><div className="toast-tag">SYSTEM // {toast.kind === "error" ? "ALERT" : "ANNOUNCEMENT"}</div><button onClick={() => setToast(null)} aria-label="Close notification"><X /></button><strong>{toast.title}</strong><p>{toast.message}</p><div className="toast-scan" /></div>}
  </div>;
}
