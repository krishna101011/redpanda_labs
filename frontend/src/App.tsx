import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  Activity, ArrowDownToLine, ArrowLeft, ArrowRight, BookOpen, Bot, Check, CheckCircle2,
  ChevronDown, ChevronRight, CircleHelp, Clock3, Code2, Database, FileCode2, FileText,
  FlaskConical, Gauge, GitBranch, GraduationCap, HardDrive, Home, Info, KeyRound, Lightbulb,
  ListFilter, LockKeyhole, Menu, Network, Plus, RefreshCw, RotateCcw, Search, Settings2,
  Shield, ShieldCheck, Sparkles, TerminalSquare, Trash2, Upload, Waypoints, Wrench, X,
} from 'lucide-react';
import { api, download, type Challenge, type Note } from './api';
import { TerminalPanel } from './components/TerminalPanel';
import { Modal } from './components/Modal';

type View = 'home' | 'path' | 'missions' | 'workspace' | 'notebook' | 'builder' | 'settings';
type Diagnostic = { docker: { available: boolean; image_ready: boolean; warning?: string | null; docker_version?: string | null }; frontend: { built: boolean; node: string | null; npm: string | null }; database: { status: string }; storage: { free_bytes: number }; release_ready: boolean; release_note: string };
type Notice = { tone: 'success' | 'error' | 'info'; message: string };

const LAB_IMAGE = 'redpanda-labs:0.1.0';

const navItems: { id: View; label: string; icon: typeof Home; eyebrow?: string }[] = [
  { id: 'home', label: 'Overview', icon: Home },
  { id: 'path', label: 'Learning path', icon: GitBranch },
  { id: 'missions', label: 'Wargames', icon: FlaskConical },
  { id: 'notebook', label: 'Notebook', icon: BookOpen },
  { id: 'builder', label: 'Challenge Builder', icon: FileCode2 },
  { id: 'settings', label: 'Settings & Lab', icon: Settings2 },
];
const trackShort: Record<string, string> = { 'Linux & Bash': 'LINUX', Python: 'PYTHON', Networking: 'NETWORK', 'Web Security': 'WEB SECURITY', 'Security Fundamentals': 'SECURITY', 'Integrated Capstone': 'CAPSTONE' };
const difficultyTone = (value: string) => value === 'Beginner' ? 'beginner' : value === 'Intermediate' ? 'intermediate' : 'advanced';
const stateLabel: Record<string, string> = { locked: 'Locked', available: 'Available', in_progress: 'In progress', completed: 'Completed' };

export default function App() {
  const [view, setView] = useState<View>('home');
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [overall, setOverall] = useState({ completed: 0, total: 15, in_progress: 0 });
  const [selectedId, setSelectedId] = useState('challenge-01');
  const [diagnostics, setDiagnostics] = useState<Diagnostic | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [achievements, setAchievements] = useState<{ id: string; title: string; detail: string; achieved_at: string }[]>([]);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [loading, setLoading] = useState(true);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [modal, setModal] = useState<'note' | 'docs' | null>(null);

  const selectedChallenge = useMemo(() => challenges.find((challenge) => challenge.id === selectedId) ?? null, [challenges, selectedId]);
  const refreshChallenges = useCallback(async () => {
    const response = await api<{ items: Challenge[]; overall: typeof overall }>('/api/challenges');
    setChallenges(response.items); setOverall(response.overall);
  }, []);
  const refreshDiagnostics = useCallback(async () => {
    const response = await api<Diagnostic>('/api/diagnostics'); setDiagnostics(response);
  }, []);
  const refreshNotes = useCallback(async () => {
    const response = await api<{ items: Note[] }>('/api/notes'); setNotes(response.items);
  }, []);
  const refreshAchievements = useCallback(async () => {
    const response = await api<{ items: typeof achievements }>('/api/achievements'); setAchievements(response.items);
  }, []);
  const refreshAll = useCallback(async () => {
    setLoading(true);
    const jobs = await Promise.allSettled([refreshChallenges(), refreshDiagnostics(), refreshNotes(), refreshAchievements()]);
    const failed = jobs.find((job) => job.status === 'rejected');
    if (failed?.status === 'rejected') setNotice({ tone: 'error', message: failed.reason instanceof Error ? failed.reason.message : 'Some local data could not be loaded.' });
    setLoading(false);
  }, [refreshChallenges, refreshDiagnostics, refreshNotes, refreshAchievements]);
  useEffect(() => { void refreshAll(); }, [refreshAll]);

  const openChallenge = (challenge: Challenge, launch = false) => {
    if (challenge.locked) {
      setNotice({ tone: 'info', message: `Complete the prerequisite mission${challenge.prerequisites_missing.length === 1 ? '' : 's'} first: ${challenge.prerequisites_missing.map((id) => challenges.find((item) => item.id === id)?.title ?? id).join(', ')}.` });
      return;
    }
    setSelectedId(challenge.id); setView('workspace');
    if (launch) void startChallenge(challenge.id);
  };

  const startChallenge = async (id: string) => {
    try {
      const response = await api<{ message: string }>(`/api/challenges/${id}/start`, { method: 'POST' });
      setNotice({ tone: 'success', message: response.message }); await refreshAll();
    } catch (error) {
      setNotice({ tone: 'error', message: error instanceof Error ? error.message : 'Lab could not be started.' });
    }
  };
  const pushNotice = (tone: Notice['tone'], message: string) => setNotice({ tone, message });

  return <div className={`app-shell ${navCollapsed ? 'nav-collapsed' : ''}`}>
    <aside className="sidebar">
      <div className="brand-row"><div className="brand-mark" aria-hidden="true"><span/><span/><span/></div>{!navCollapsed && <div className="brand-copy"><strong>redpanda<span> labs</span></strong><small>SECURITY WORKSHOP</small></div>}<button className="sidebar-toggle" onClick={() => setNavCollapsed((value) => !value)} aria-label="Collapse navigation"><Menu size={16}/></button></div>
      {!navCollapsed && <div className="sidebar-label">WORKSPACE</div>}
      <nav className="main-nav" aria-label="Main navigation">
        {navItems.map((item) => <button key={item.id} className={`nav-item ${view === item.id || (view === 'workspace' && item.id === 'missions') ? 'nav-item--active' : ''}`} onClick={() => setView(item.id)} title={navCollapsed ? item.label : undefined}>
          <item.icon size={17} strokeWidth={1.8}/>{!navCollapsed && <span>{item.label}</span>}{!navCollapsed && item.id === 'missions' && <small className="nav-count">15</small>}
        </button>)}
      </nav>
      {!navCollapsed && <div className="sidebar-bottom">
        <div className="side-progress"><div className="side-progress-head"><span>LEARNING PROGRESS</span><span>{overall.completed}/15</span></div><div className="progress-track"><i style={{ width: `${Math.min(100, overall.completed / 15 * 100)}%` }}/></div><p>{overall.completed === 0 ? 'Your first mission is waiting.' : `${Math.round(overall.completed / 15 * 100)}% of the built-in path mastered`}</p></div>
        <button className="side-help" onClick={() => setModal('docs')}><CircleHelp size={16}/><span>Quick help</span><ArrowRight size={14}/></button>
        <div className="profile-mini"><div className="profile-avatar">RP</div><div><strong>Local learner</strong><small>Single-user workspace</small></div><span className="online-dot"/></div>
      </div>}
    </aside>

    <main className="main-content">
      <header className="topbar"><div className="breadcrumbs"><span>REDPANDA LABS</span><ChevronRight size={13}/><strong>{view === 'workspace' ? selectedChallenge?.title ?? 'Mission workspace' : navItems.find((item) => item.id === view)?.label ?? 'Overview'}</strong></div>
        <div className="topbar-right"><span className={`environment-pill ${diagnostics?.docker.available && diagnostics.docker.image_ready ? 'environment-pill--ready' : 'environment-pill--warning'}`}><i/>{diagnostics?.docker.available && diagnostics.docker.image_ready ? 'LAB READY' : 'LAB NOT READY'}</span><button className="icon-button top-refresh" onClick={() => void refreshAll()} title="Refresh local status"><RefreshCw size={15}/></button><div className="avatar-small">R</div></div>
      </header>
      {notice && <div className={`notice notice--${notice.tone}`} role="status"><span>{notice.tone === 'error' ? <Info size={16}/> : notice.tone === 'success' ? <CheckCircle2 size={16}/> : <Lightbulb size={16}/>}</span><p>{notice.message}</p><button onClick={() => setNotice(null)} aria-label="Dismiss notice"><X size={15}/></button></div>}
      <div className="page-body">
        {view === 'home' && <Dashboard challenges={challenges} overall={overall} diagnostics={diagnostics} achievements={achievements} loading={loading} onOpen={openChallenge} onNavigate={setView} onHelp={() => setModal('docs')}/>}
        {view === 'path' && <LearningPath challenges={challenges} onOpen={(item) => openChallenge(item, !item.locked)}/>}
        {view === 'missions' && <Missions challenges={challenges} onOpen={(item) => openChallenge(item, !item.locked)}/>}
        {view === 'workspace' && selectedChallenge && <Workspace challenge={selectedChallenge} diagnostics={diagnostics} onStart={() => void startChallenge(selectedChallenge.id)} onRefresh={refreshAll} onNotice={pushNotice} onOpenNote={() => setModal('note')} onOpenDocs={() => setModal('docs')}/>}
        {view === 'workspace' && !selectedChallenge && <EmptyState title="Choose a mission" body="Open the wargames catalogue and select an available mission." action="Browse missions" onAction={() => setView('missions')}/>}
        {view === 'notebook' && <Notebook notes={notes} challenges={challenges} onChanged={refreshNotes} onNotice={pushNotice}/>}
        {view === 'builder' && <Builder onNotice={pushNotice} onRefresh={refreshAll}/>}
        {view === 'settings' && <SettingsPage diagnostics={diagnostics} onNotice={pushNotice} onRefresh={refreshAll}/>}
      </div>
      <footer className="app-footer"><span><span className="footer-dot"/>LOCAL-FIRST · NO TELEMETRY</span><span>RedPanda Labs <b>v0.1.0</b></span><button onClick={() => setModal('docs')}>Help & documentation <ArrowRight size={12}/></button></footer>
    </main>
    {modal === 'note' && <NewNoteModal challenge={selectedChallenge} onClose={() => setModal(null)} onSaved={async () => { setModal(null); await refreshNotes(); pushNotice('success', 'Your note was saved to the local notebook.'); }} />}
    {modal === 'docs' && <Modal title="RedPanda Labs · quick guide" onClose={() => setModal(null)} wide><div className="quick-guide">
      <div className="guide-notice"><ShieldCheck size={19}/><div><strong>Local-first learning</strong><p>Mission commands run in a restricted Docker container, not directly in your ordinary Linux Mint shell. The Docker daemon still belongs to your computer, so container isolation is a safety layer, not a perfect boundary.</p></div></div>
      <h3>Start here</h3><ol><li>Run <code>bash scripts/setup.sh</code> once from the extracted project folder.</li><li>Run <code>bash scripts/run.sh</code>, then open <code>http://127.0.0.1:8000</code>.</li><li>Choose Challenge 01, launch its lab, use the terminal to investigate, then press <b>Check objective</b>.</li></ol>
      <h3>When Docker is unavailable</h3><p>You can still read mission guides and offline hints, maintain notebook entries, and explore the catalogue. Practical shell execution requires Docker and the local lab image. Use Settings → Diagnostics to inspect readiness.</p>
      <h3>Keep operations separate</h3><p><b>Restart shell</b> ends the current Bash process but keeps files. <b>Reset workspace</b> restores one challenge's files and removes that challenge's lab process. <b>Reset progress</b> clears current completion state but keeps notes and workspaces. Data deletion is a separate, explicitly confirmed operation.</p>
      <h3>Privacy note</h3><p>Offline hints need no AI provider. If AI is configured, selected terminal output is sent only after you review and confirm it. API credentials are stored in a private configuration file outside the project and are not included in exports.</p>
      <div className="guide-actions"><button className="btn btn-secondary" onClick={() => { setModal(null); setView('settings'); }}>Open Settings</button><button className="btn btn-primary" onClick={() => { setModal(null); setView('missions'); }}>Browse missions <ArrowRight size={15}/></button></div>
    </div></Modal>}
  </div>;
}

function Dashboard({ challenges, overall, diagnostics, achievements, loading, onOpen, onNavigate, onHelp }: { challenges: Challenge[]; overall: { completed: number; total: number; in_progress: number }; diagnostics: Diagnostic | null; achievements: { id: string; title: string; detail: string; achieved_at: string }[]; loading: boolean; onOpen: (challenge: Challenge, launch?: boolean) => void; onNavigate: (view: View) => void; onHelp: () => void }) {
  const next = challenges.find((challenge) => challenge.state === 'in_progress') ?? challenges.find((challenge) => !challenge.locked && challenge.state !== 'completed') ?? challenges[0];
  const recentCompleted = [...challenges].filter((challenge) => challenge.state === 'completed').slice(-3).reverse();
  const tracks = useMemo(() => [...new Set(challenges.map((challenge) => challenge.track))].map((track) => ({ track, total: challenges.filter((item) => item.track === track).length, completed: challenges.filter((item) => item.track === track && item.state === 'completed').length })), [challenges]);
  return <>
    <section className="welcome-row"><div><div className="eyebrow"><Sparkles size={13}/> YOUR LOCAL TRAINING ENVIRONMENT</div><h1>Build skill. <span>Verify evidence.</span></h1><p className="lead">A practical path through Linux, Python, networking, and application security.</p><div className="welcome-actions"><button className="btn btn-primary" onClick={() => next && onOpen(next, !next.locked)} disabled={!next}><TerminalSquare size={16}/>{overall.in_progress ? 'Continue mission' : overall.completed ? 'Continue learning' : 'Start first mission'}<ArrowRight size={15}/></button><button className="btn btn-secondary" onClick={() => onNavigate('path')}><Waypoints size={15}/> View learning path</button></div></div><PandaEmblem/></section>
    {!diagnostics?.docker.available || !diagnostics.docker.image_ready ? <div className="runtime-alert"><div className="runtime-alert-icon"><HardDrive size={18}/></div><div><strong>Lab runtime needs setup</strong><p>{diagnostics?.docker.warning ?? 'Run the setup script to build the lab image and check Docker access.'}</p></div><button className="btn btn-secondary btn-small" onClick={() => onNavigate('settings')}>Open diagnostics <ArrowRight size={13}/></button></div> : <div className="runtime-alert runtime-alert--ready"><div className="runtime-alert-icon"><ShieldCheck size={18}/></div><div><strong>Local lab runtime is available</strong><p>New workspaces use isolated containers, persistent volumes, and resource limits.</p></div><span className="small-status"><i/> {diagnostics.docker.docker_version ?? 'Docker'}</span></div>}
    <div className="section-heading section-heading--stats"><div><div className="eyebrow">YOUR LEARNING SNAPSHOT</div><h2>At a glance</h2></div><button className="text-link" onClick={() => onNavigate('missions')}>All missions <ArrowRight size={13}/></button></div>
    <div className="stats-grid">
      <StatCard icon={CheckCircle2} label="Missions completed" value={`${overall.completed} / ${overall.total}`} detail={`${Math.round(overall.completed / Math.max(overall.total, 1) * 100)}% of core curriculum`} progress={overall.completed / Math.max(overall.total, 1) * 100}/>
      <StatCard icon={Activity} label="In progress" value={String(overall.in_progress)} detail={overall.in_progress ? 'Pick up where you left off' : 'Ready when you are'} accent="orange"/>
      <StatCard icon={GraduationCap} label="Mastery badges" value={String(achievements.length)} detail={achievements.length ? 'Earned through verified work' : 'Checks, not clicks, earn mastery'} accent="violet"/>
      <StatCard icon={Database} label="Storage available" value={diagnostics ? formatBytes(diagnostics.storage.free_bytes) : '—'} detail="On this computer" accent="teal"/>
    </div>
    <div className="dashboard-grid">
      <section className="content-card continue-card"><div className="card-topline"><span className="eyebrow">RECOMMENDED NEXT</span><span className={`difficulty difficulty--${difficultyTone(next?.difficulty ?? 'Beginner')}`}>{next?.difficulty ?? 'Beginner'}</span></div><div className="continue-art"><div className="art-lines"/><div className="mission-number">{next ? next.id.slice(-2) : '01'}</div><div className="art-terminal"><span/><span/><span/><div>redpanda@lab:~$ _</div></div></div><div className="track-kicker">{next ? trackShort[next.track] ?? next.track.toUpperCase() : 'LINUX BASICS'}</div><h3>{next?.title ?? 'First Contact'}</h3><p>{next?.summary ?? 'Get comfortable with your lab workspace.'}</p><div className="mission-meta"><span><Clock3 size={13}/>{next?.estimated_minutes ?? 10} min estimate</span><span><BookOpen size={13}/>{next?.learning_objectives.length ?? 4} objectives</span></div><button className="btn btn-primary btn-block" onClick={() => next && onOpen(next, !next.locked)} disabled={!next || Boolean(next.locked)}> {next?.state === 'in_progress' ? 'Continue mission' : next?.state === 'completed' ? 'Review mission' : 'Open mission'} <ArrowRight size={15}/></button></section>
      <section className="content-card track-card"><div className="card-heading"><div><div className="eyebrow">CURRICULUM MAP</div><h3>Track progress</h3></div><button className="icon-button" onClick={() => onNavigate('path')} title="Open learning path"><ArrowRight size={15}/></button></div><div className="track-list">{tracks.map((item, index) => <div className="track-row" key={item.track}><div className={`track-icon track-icon--${index % 5}`}><TrackIcon name={item.track}/></div><div className="track-row-main"><div className="track-row-title"><span>{item.track}</span><b>{item.completed}/{item.total}</b></div><div className="progress-track"><i style={{ width: `${item.completed / item.total * 100}%` }}/></div></div></div>)}</div><button className="text-link track-link" onClick={() => onNavigate('path')}>Explore skill tree <ArrowRight size={13}/></button></section>
    </div>
    <div className="dashboard-grid dashboard-grid--lower">
      <section className="content-card recent-card"><div className="card-heading"><div><div className="eyebrow">YOUR HISTORY</div><h3>Recently mastered</h3></div><button className="text-link" onClick={() => onNavigate('missions')}>View all</button></div>
        {recentCompleted.length ? <div className="recent-list">{recentCompleted.map((challenge) => <button className="recent-item" key={challenge.id} onClick={() => onOpen(challenge)}><span className="recent-check"><Check size={14}/></span><span className="recent-main"><strong>{challenge.title}</strong><small>{challenge.track}</small></span><span className="recent-state">COMPLETED</span><ChevronRight size={14}/></button>)}</div> : <div className="empty-inline"><div className="empty-icon"><BookOpen size={19}/></div><div><strong>{loading ? 'Loading learning history…' : 'Your first verified win goes here'}</strong><p>Complete an objective in the real lab to record mastery.</p></div></div>}
      </section>
      <section className="content-card setup-card"><div className="card-heading"><div><div className="eyebrow">SYSTEM CHECK</div><h3>Lab status</h3></div><button className="icon-button" onClick={() => onNavigate('settings')} title="Open diagnostics"><Wrench size={15}/></button></div><div className="check-list"><CheckRow label="Local application" status="ready" detail="Running in your browser"/><CheckRow label="Local database" status={diagnostics?.database.status === 'connected' ? 'ready' : 'waiting'} detail={diagnostics?.database.status ?? 'Checking'} /><CheckRow label="Docker daemon" status={diagnostics?.docker.available ? 'ready' : 'waiting'} detail={diagnostics?.docker.available ? 'Connected' : 'Not connected'} /><CheckRow label="Lab image" status={diagnostics?.docker.image_ready ? 'ready' : 'waiting'} detail={diagnostics?.docker.image_ready ? 'Image found' : 'Needs setup'} /></div><button className="text-link" onClick={() => onNavigate('settings')}>Run diagnostics <ArrowRight size={13}/></button></section>
    </div>
    <div className="footnote-row"><Shield size={14}/><span>Built for controlled, local learning. Only use the lab against its bundled fictional targets.</span><button onClick={onHelp}>Safety notes</button></div>
  </>;
}

function StatCard({ icon: Icon, label, value, detail, progress, accent = 'red' }: { icon: typeof CheckCircle2; label: string; value: string; detail: string; progress?: number; accent?: string }) {
  return <section className="stat-card"><div className={`stat-icon stat-icon--${accent}`}><Icon size={17}/></div><span className="stat-label">{label}</span><strong className="stat-value">{value}</strong><span className="stat-detail">{detail}</span>{progress !== undefined && <div className="stat-progress"><i style={{ width: `${progress}%` }}/></div>}</section>;
}
function CheckRow({ label, status, detail }: { label: string; status: 'ready' | 'waiting'; detail: string }) { return <div className="check-row"><span className={`check-symbol check-symbol--${status}`}>{status === 'ready' ? <Check size={12}/> : <Clock3 size={12}/>}</span><div><strong>{label}</strong><small>{detail}</small></div><span className={`check-word check-word--${status}`}>{status === 'ready' ? 'READY' : 'CHECK'}</span></div>; }
function PandaEmblem() { return <div className="panda-emblem"><div className="panda-halo"/><div className="panda-head"><span className="panda-ear panda-ear--left"/><span className="panda-ear panda-ear--right"/><span className="panda-eye panda-eye--left"/><span className="panda-eye panda-eye--right"/><span className="panda-snout"/><span className="panda-nose"/><span className="panda-cheek panda-cheek--left"/><span className="panda-cheek panda-cheek--right"/></div><span className="panda-spark panda-spark--one">✳</span><span className="panda-spark panda-spark--two">+</span></div>; }
function TrackIcon({ name }: { name: string }) { if (name === 'Python') return <Code2 size={16}/>; if (name === 'Networking') return <Network size={16}/>; if (name === 'Web Security') return <Shield size={16}/>; if (name === 'Security Fundamentals') return <LockKeyhole size={16}/>; if (name === 'Integrated Capstone') return <Waypoints size={16}/>; return <TerminalSquare size={16}/>; }

function Missions({ challenges, onOpen }: { challenges: Challenge[]; onOpen: (challenge: Challenge) => void }) {
  const [search, setSearch] = useState(''); const [track, setTrack] = useState('all'); const [difficulty, setDifficulty] = useState('all'); const [status, setStatus] = useState('all');
  const tracks = [...new Set(challenges.map((item) => item.track))];
  const filtered = challenges.filter((item) => (!search || `${item.title} ${item.summary} ${item.tags.join(' ')}`.toLowerCase().includes(search.toLowerCase())) && (track === 'all' || item.track === track) && (difficulty === 'all' || item.difficulty === difficulty) && (status === 'all' || item.state === status));
  const groups = [...new Set(filtered.map((item) => item.track))];
  return <><PageIntro eyebrow="FIELD GUIDE / 15 MISSIONS" title="Wargames catalogue" subtitle="Fifteen purpose-built exercises. Each mission has its own evidence, offline hints, and completion check." trailing={<span className="total-pill"><FlaskConical size={14}/>{challenges.length} missions</span>}/>
    <div className="filter-bar"><div className="search-field"><Search size={16}/><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search missions, skills, or tags…" aria-label="Search missions"/>{search && <button onClick={() => setSearch('')} aria-label="Clear search"><X size={13}/></button>}</div><label className="filter-select"><ListFilter size={14}/><select value={track} onChange={(event) => setTrack(event.target.value)} aria-label="Filter by track"><option value="all">All tracks</option>{tracks.map((value) => <option key={value}>{value}</option>)}</select><ChevronDown size={13}/></label><label className="filter-select"><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} aria-label="Filter by difficulty"><option value="all">All levels</option><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select><ChevronDown size={13}/></label><label className="filter-select"><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by status"><option value="all">All status</option><option value="locked">Locked</option><option value="available">Available</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select><ChevronDown size={13}/></label></div>
    <div className="catalog-count"><span>SHOWING <b>{filtered.length}</b> OF {challenges.length} MISSIONS</span><span><span className="tiny-dot tiny-dot--red"/> Built-in curriculum <span className="catalog-separator">·</span> no AI key required</span></div>
    {filtered.length ? groups.map((group) => <section className="catalog-group" key={group}><div className="group-heading"><div className="group-track-icon"><TrackIcon name={group}/></div><h2>{group}</h2><span>{filtered.filter((item) => item.track === group).length} missions</span></div><div className="mission-grid">{filtered.filter((item) => item.track === group).map((challenge) => <MissionCard key={challenge.id} challenge={challenge} onOpen={() => onOpen(challenge)}/>)}</div></section>) : <EmptyState title="No missions match those filters" body="Try another topic or clear the search term." action="Clear filters" onAction={() => { setSearch(''); setTrack('all'); setDifficulty('all'); setStatus('all'); }}/>} 
  </>;
}
function MissionCard({ challenge, onOpen }: { challenge: Challenge; onOpen: () => void }) {
  return <article className={`mission-card ${challenge.locked ? 'mission-card--locked' : ''}`}><div className="mission-card-head"><span className="mission-id">{challenge.id.replace('challenge-', 'RP-')}</span><span className={`state-pill state-pill--${challenge.state}`}>{challenge.state === 'completed' ? <CheckCircle2 size={12}/> : challenge.locked ? <LockKeyhole size={11}/> : challenge.state === 'in_progress' ? <Activity size={12}/> : <span/>}{stateLabel[challenge.state]}</span></div><div className="mission-card-symbol"><TrackIcon name={challenge.track}/></div><h3>{challenge.title}</h3><p>{challenge.summary}</p><div className="mission-card-tags"><span className={`difficulty difficulty--${difficultyTone(challenge.difficulty)}`}>{challenge.difficulty}</span><span><Clock3 size={12}/>{challenge.estimated_minutes} min</span></div><div className="mission-card-footer">{challenge.locked ? <small><LockKeyhole size={12}/> {challenge.prerequisites_missing.length} prerequisite{challenge.prerequisites_missing.length === 1 ? '' : 's'} remaining</small> : <small>{challenge.learning_objectives.length} learning objectives</small>}<button onClick={onOpen} disabled={challenge.locked} aria-label={`Open ${challenge.title}`}>{challenge.state === 'completed' ? 'Review' : challenge.state === 'in_progress' ? 'Continue' : challenge.locked ? 'Locked' : 'Open'} <ArrowRight size={13}/></button></div></article>;
}

function LearningPath({ challenges, onOpen }: { challenges: Challenge[]; onOpen: (challenge: Challenge) => void }) {
  const tracks = [...new Set(challenges.map((item) => item.track))];
  return <><PageIntro eyebrow="GUIDED CURRICULUM" title="The learning path" subtitle="Follow prerequisites where they matter. Optional branches stay optional, and each completed objective unlocks eligible missions." trailing={<span className="total-pill"><Waypoints size={14}/> Skill tree</span>}/>
    <div className="path-legend"><span><i className="legend-dot legend-dot--done"/> Completed</span><span><i className="legend-dot legend-dot--active"/> Available</span><span><i className="legend-dot legend-dot--locked"/> Locked by prerequisites</span></div>
    <div className="path-overview"><div><span className="eyebrow">CORE CURRICULUM</span><strong>{challenges.filter((item) => item.state === 'completed').length} <small>/ {challenges.length} mastered</small></strong><div className="progress-track"><i style={{ width: `${challenges.filter((item) => item.state === 'completed').length / Math.max(challenges.length, 1) * 100}%` }}/></div></div><p>Read the prerequisites on each node to understand why a mission is locked. Capstones bring together several earlier skills.</p></div>
    <div className="path-tracks">{tracks.map((track, trackIndex) => <section className="path-track-card" key={track}><div className="path-track-head"><div className={`track-icon track-icon--${trackIndex % 5}`}><TrackIcon name={track}/></div><div><h2>{track}</h2><p>{challenges.filter((item) => item.track === track).filter((item) => item.state === 'completed').length} of {challenges.filter((item) => item.track === track).length} complete</p></div></div><div className="path-nodes">{challenges.filter((item) => item.track === track).map((challenge) => <div className={`path-node path-node--${challenge.state}`} key={challenge.id}><span className="path-connector"/><button className="path-node-marker" onClick={() => !challenge.locked && onOpen(challenge)} disabled={challenge.locked} aria-label={`${challenge.title}: ${stateLabel[challenge.state]}`}>{challenge.state === 'completed' ? <Check size={15}/> : challenge.locked ? <LockKeyhole size={13}/> : <span>{challenge.id.slice(-2)}</span>}</button><button className="path-node-content" onClick={() => onOpen(challenge)} disabled={challenge.locked}><span className="path-node-state">{stateLabel[challenge.state]}</span><strong>{challenge.title}</strong><small>{challenge.summary}</small>{challenge.prerequisites.length > 0 && <span className="path-prereq">Requires {challenge.prerequisites.map((id) => challenges.find((item) => item.id === id)?.title ?? id).join(' · ')}</span>}</button><span className={`path-node-diff difficulty difficulty--${difficultyTone(challenge.difficulty)}`}>{challenge.difficulty}</span></div>)}</div></section>)}</div>
    <div className="callout-row"><div className="callout-icon"><Info size={17}/></div><div><strong>How unlocking works</strong><p>A validator records completion only after it verifies challenge-specific workspace state. Opening a mission, reading a hint, or claiming success never completes it.</p></div></div>
  </>;
}

function PageIntro({ eyebrow, title, subtitle, trailing }: { eyebrow: string; title: string; subtitle: string; trailing?: ReactNode }) { return <section className="page-intro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{trailing}</section>; }
function EmptyState({ title, body, action, onAction }: { title: string; body: string; action: string; onAction: () => void }) { return <div className="empty-state"><div className="empty-state-icon"><Search size={22}/></div><h2>{title}</h2><p>{body}</p><button className="btn btn-secondary" onClick={onAction}>{action} <ArrowRight size={14}/></button></div>; }
function formatBytes(value: number) { if (!Number.isFinite(value)) return '—'; const units = ['B','KB','MB','GB','TB']; let index = 0, size = value; while (size >= 1024 && index < units.length - 1) { size /= 1024; index++; } return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`; }

function Workspace({ challenge, diagnostics, onStart, onRefresh, onNotice, onOpenNote, onOpenDocs }: { challenge: Challenge; diagnostics: Diagnostic | null; onStart: () => void; onRefresh: () => Promise<void>; onNotice: (tone: Notice['tone'], message: string) => void; onOpenNote: () => void; onOpenDocs: () => void }) {
  const [hint, setHint] = useState<{ level: number; title: string; content: string } | null>(null);
  const [validation, setValidation] = useState<{ valid: boolean; feedback: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false); const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftWidth, setLeftWidth] = useState(286); const [rightWidth, setRightWidth] = useState(326);
  const [terminalStatus, setTerminalStatus] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [selectedOutput, setSelectedOutput] = useState(''); const [question, setQuestion] = useState(''); const [answer, setAnswer] = useState<{ answer: string; source: string } | null>(null);
  const [explanation, setExplanation] = useState<{ explanation: string; source: string } | null>(null);
  const [aiConfigured, setAiConfigured] = useState(false);
  const [terminalEpoch, setTerminalEpoch] = useState(0);
  const [dragging, setDragging] = useState<'left' | 'right' | null>(null);
  const handleTerminalStatus = useCallback((status: 'connecting' | 'connected' | 'error') => setTerminalStatus(status), []);
  const handleSelection = useCallback((text: string) => setSelectedOutput(text.slice(0, 8000)), []);

  useEffect(() => { void api<{ configured: boolean }>('/api/ai/settings').then((result) => setAiConfigured(result.configured)).catch(() => setAiConfigured(false)); }, []);
  useEffect(() => {
    if (!dragging) return;
    const move = (event: PointerEvent) => {
      const grid = document.querySelector('.workspace-grid') as HTMLElement | null;
      if (!grid) return;
      const rect = grid.getBoundingClientRect();
      if (dragging === 'left') setLeftWidth(Math.max(220, Math.min(450, event.clientX - rect.left)));
      else setRightWidth(Math.max(260, Math.min(470, rect.right - event.clientX)));
    };
    const stop = () => setDragging(null);
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', stop); window.addEventListener('pointercancel', stop);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', stop); window.removeEventListener('pointercancel', stop); };
  }, [dragging]);

  const requestHint = async () => {
    setBusy(true);
    try { const result = await api<{ hint: { level: number; title: string; content: string } }>(`/api/challenges/${challenge.id}/hint`, { method: 'POST' }); setHint(result.hint); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not load the offline hint.'); }
    finally { setBusy(false); }
  };
  const checkObjective = async () => {
    setBusy(true);
    try {
      const result = await api<{ valid: boolean; feedback: string[] }>(`/api/challenges/${challenge.id}/validate`, { method: 'POST' });
      setValidation(result); onNotice(result.valid ? 'success' : 'info', result.valid ? `Objective verified for “${challenge.title}”.` : result.feedback.join(' '));
      await onRefresh();
    } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not validate the objective.'); }
    finally { setBusy(false); }
  };
  const restartShell = async () => {
    const typed = window.prompt(`This ends the current Bash process but keeps ${challenge.id}'s files. Type ${challenge.id} to continue.`);
    if (typed !== challenge.id) return;
    setBusy(true);
    try { const result = await api<{ message: string }>(`/api/challenges/${challenge.id}/restart-shell`, { method: 'POST', body: JSON.stringify({ confirmation: typed }) }); setTerminalEpoch((value) => value + 1); setTerminalStatus('connecting'); onNotice('success', result.message); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Shell restart failed.'); }
    finally { setBusy(false); }
  };
  const resetWorkspace = async () => {
    const typed = window.prompt(`This restores ${challenge.id} to its initial state and deletes files created in this workspace. Notes, historical completions, and other challenges remain. Type ${challenge.id} to continue.`);
    if (typed !== challenge.id) return;
    setBusy(true);
    try { const result = await api<{ reset: boolean }>(`/api/challenges/${challenge.id}/reset`, { method: 'POST', body: JSON.stringify({ confirmation: typed }) }); setTerminalEpoch((value) => value + 1); setHint(null); setValidation(null); setTerminalStatus('connecting'); onNotice('success', result.reset ? 'Workspace reset. Notes and completion history were preserved.' : 'Workspace reset did not complete.'); await onRefresh(); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Workspace reset failed.'); }
    finally { setBusy(false); }
  };
  const getMentorAnswer = async () => {
    if (!question.trim()) { onNotice('info', 'Enter a question for your mentor first.'); return; }
    setBusy(true); setAnswer(null);
    try {
      let share = false;
      if (selectedOutput.trim() && aiConfigured) {
        const preview = selectedOutput.slice(0, 700).replace(/\n/g, ' ');
        share = window.confirm(`Your configured AI endpoint will receive this selected terminal output with your question.\n\nEndpoint: ${await api<{ base_url: string }>('/api/ai/settings').then((item) => item.base_url)}\n\nPreview: ${preview}${selectedOutput.length > 700 ? '…' : ''}\n\nShare this selection?`);
      }
      const result = await api<{ answer: string; source: string }>('/api/mentor/ask', { method: 'POST', body: JSON.stringify({ question: question.trim(), challenge_id: challenge.id, selected_output: share ? selectedOutput : null, share_selected_output: share }) });
      setAnswer(result);
    } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Mentor request failed.'); }
    finally { setBusy(false); }
  };
  const explainSelection = async () => {
    if (!selectedOutput.trim()) { onNotice('info', 'Select a short section of terminal output first, then choose Explain selection.'); return; }
    let shareConfirmed = false;
    if (aiConfigured) shareConfirmed = window.confirm(`Share this selected text with your configured AI endpoint?\n\n${selectedOutput.slice(0, 700)}${selectedOutput.length > 700 ? '…' : ''}`);
    setBusy(true); setExplanation(null);
    try { const result = await api<{ explanation: string; source: string }>('/api/mentor/explain', { method: 'POST', body: JSON.stringify({ text: selectedOutput, challenge_id: challenge.id, use_ai: aiConfigured && shareConfirmed, share_confirmed: shareConfirmed }) }); setExplanation(result); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not explain the selected output.'); }
    finally { setBusy(false); }
  };
  const saveExplanation = async () => {
    if (!explanation) return;
    try { await api('/api/notes/explanations', { method: 'POST', body: JSON.stringify({ title: `Explanation: ${challenge.title}`, content: explanation.explanation, challenge_id: challenge.id, tags: ['saved-explanation', challenge.track.toLowerCase()] }) }); onNotice('success', 'Explanation saved as a separate notebook entry.'); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not save explanation.'); }
  };

  return <><div className="workspace-page-head"><div><div className="eyebrow">MISSION WORKSPACE / {challenge.id.toUpperCase()}</div><h1>{challenge.title}</h1><p>{challenge.summary}</p></div><div className="workspace-head-actions"><span className={`state-pill state-pill--${challenge.state}`}>{challenge.state === 'completed' ? <CheckCircle2 size={12}/> : <Activity size={12}/>} {stateLabel[challenge.state]}</span><button className="btn btn-secondary btn-small" onClick={onOpenDocs}><BookOpen size={14}/> Mission guide</button></div></div>
    {!diagnostics?.docker.available || !diagnostics.docker.image_ready ? <div className="runtime-alert runtime-alert--compact"><div className="runtime-alert-icon"><HardDrive size={17}/></div><div><strong>Terminal runtime is unavailable</strong><p>Read the mission and offline hints here; practical commands need Docker and the built lab image.</p></div><button className="btn btn-secondary btn-small" onClick={onStart}>Check lab setup <ArrowRight size={13}/></button></div> : null}
    <div className={`workspace-grid ${leftCollapsed ? 'workspace-grid--left-collapsed' : ''} ${rightCollapsed ? 'workspace-grid--right-collapsed' : ''}`} style={{ '--left-panel': `${leftWidth}px`, '--right-panel': `${rightWidth}px` } as CSSProperties}>
      {!leftCollapsed && <aside className="workspace-mission-panel"><div className="panel-heading"><span><span className="panel-index">01</span> MISSION BRIEF</span><button className="icon-button" title="Collapse mission panel" onClick={() => setLeftCollapsed(true)}><ArrowLeft size={14}/></button></div><div className="mission-panel-scroll"><div className="mission-track-label">{trackShort[challenge.track] ?? challenge.track.toUpperCase()}</div><h2>{challenge.title}</h2><p className="mission-description">{challenge.description}</p><div className="mission-detail-badges"><span className={`difficulty difficulty--${difficultyTone(challenge.difficulty)}`}>{challenge.difficulty}</span><span><Clock3 size={12}/>{challenge.estimated_minutes} min</span></div>
        <div className="brief-section"><h3><TargetIcon/> Objective</h3><p>Complete the following verified outcomes. The backend checks the actual workspace state.</p><div className="objective-list">{challenge.learning_objectives.map((objective, index) => <div className="objective-row" key={objective}><span>{String(index + 1).padStart(2, '0')}</span><p>{objective}</p></div>)}</div></div>
        <div className="brief-section"><h3><GitBranch size={15}/> Prerequisites</h3>{challenge.prerequisites.length ? <div className="prereq-list">{challenge.prerequisites.map((id) => <span key={id} className="prereq-chip"><CheckCircle2 size={12}/>{id}</span>)}</div> : <p className="muted-text">No prerequisites. This is a starting point.</p>}</div>
        <div className="brief-section"><h3><BookOpen size={15}/> Concepts</h3><div className="tag-list">{challenge.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></div>
        {validation && <div className={`validation-card ${validation.valid ? 'validation-card--success' : 'validation-card--needs-work'}`}><div>{validation.valid ? <CheckCircle2 size={17}/> : <Info size={17}/>}<strong>{validation.valid ? 'Objective verified' : 'Not there yet'}</strong></div>{validation.feedback.map((line) => <p key={line}>{line}</p>)}{validation.valid && <p>{challenge.completion_explanation}</p>}</div>}
        {challenge.progress.latest_feedback && !validation && <div className="last-feedback"><Info size={14}/><span>{challenge.progress.latest_feedback}</span></div>}
      </div><div className="mission-panel-actions"><button className="btn btn-primary btn-block" onClick={checkObjective} disabled={busy}><ShieldCheck size={15}/>{busy ? 'Checking…' : 'Check objective'}<ArrowRight size={14}/></button><div className="workspace-action-row"><button className="btn btn-quiet" onClick={requestHint} disabled={busy}><Lightbulb size={14}/> Next hint</button><button className="btn btn-quiet" onClick={onOpenNote}><FileText size={14}/> Save note</button></div></div></aside>}
      {leftCollapsed && <button className="restore-panel restore-panel--left" onClick={() => setLeftCollapsed(false)} title="Show mission panel"><ChevronRight size={15}/><span>MISSION</span></button>}
      {!leftCollapsed && <div className="split-handle" role="separator" aria-label="Resize mission panel" onPointerDown={() => setDragging('left')} />}
      <div className="workspace-terminal-column"><TerminalPanel key={`${challenge.id}-${terminalEpoch}`} challengeId={challenge.id} onStatus={handleTerminalStatus} onSelectionChange={handleSelection}/><div className="terminal-toolbar"><span className={`shell-status ${terminalStatus === 'connected' ? 'shell-status--connected' : terminalStatus === 'error' ? 'shell-status--error' : ''}`}><i/>{terminalStatus === 'connected' ? 'Shell attached' : terminalStatus === 'error' ? 'Shell unavailable' : 'Connecting to lab'}</span><div><button className="text-action" onClick={restartShell} disabled={busy}><RotateCcw size={13}/> Restart shell</button><button className="text-action text-action--danger" onClick={resetWorkspace} disabled={busy}><Trash2 size={13}/> Reset workspace</button></div></div>
        <div className="selection-strip"><span><span className="selection-indicator"/> {selectedOutput ? `${selectedOutput.length} characters selected` : 'Select terminal output to explain it'}</span><button onClick={explainSelection} disabled={!selectedOutput || busy}><Sparkles size={13}/> Explain selection</button></div>
      </div>
      {!rightCollapsed && <div className="split-handle" role="separator" aria-label="Resize mentor panel" onPointerDown={() => setDragging('right')} />}
      {!rightCollapsed && <aside className="mentor-panel"><div className="panel-heading"><span><span className="panel-index panel-index--mentor">02</span> AI MENTOR</span><button className="icon-button" title="Collapse mentor panel" onClick={() => setRightCollapsed(true)}><ArrowRight size={14}/></button></div><div className="mentor-scroll"><div className="mentor-profile"><div className="mentor-avatar"><Bot size={18}/></div><div><strong>RedPanda guide</strong><span><i/>{aiConfigured ? 'AI provider configured' : 'Offline mode · private'}</span></div></div><div className="mentor-callout"><Sparkles size={14}/><p>{aiConfigured ? 'Ask a focused question. Only your question and essential mission context are sent. Selected output is sent only after you confirm.' : 'Your offline mentor is ready. Three progressive mission hints and command explanations work without an API key.'}</p></div>
        <div className="mentor-section-title"><span>PROGRESSIVE HINTS</span><span>LEVEL {hint?.level ?? challenge.progress.hint_level}/3</span></div>
        {hint ? <div className="hint-card"><div><span>HINT {hint.level}</span><strong>{hint.title}</strong></div><p>{hint.content}</p></div> : <div className="hint-empty"><Lightbulb size={18}/><p>Try the task yourself first. Request a nudge when you need one.</p><button className="btn btn-secondary btn-small" onClick={requestHint} disabled={busy}>Request next hint <ArrowRight size={13}/></button></div>}
        {hint && <button className="mentor-secondary-action" onClick={requestHint} disabled={busy || hint.level >= 3}>{hint.level >= 3 ? 'All three offline hints revealed' : 'Need a little more help?'} <ArrowRight size={13}/></button>}
        <div className="mentor-section-title"><span>ASK THE MENTOR</span><span><Sparkles size={12}/> {aiConfigured ? 'PROVIDER' : 'OFFLINE'}</span></div><label className="field-label" htmlFor="mentor-question">What are you stuck on?</label><textarea id="mentor-question" className="mentor-question" rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Example: why does chmod 640 set these permissions?"/><div className="mentor-question-foot"><span>{question.length}/4000</span><button className="btn btn-primary btn-small" onClick={getMentorAnswer} disabled={busy || !question.trim()}>Ask <ArrowRight size={13}/></button></div>
        {answer && <div className="mentor-response"><div className="mentor-response-head"><Bot size={14}/><strong>Mentor response</strong><span>{answer.source === 'offline' ? 'LOCAL' : answer.source === 'offline-fallback' ? 'FALLBACK' : 'AI'}</span></div><p>{answer.answer}</p></div>}
        {explanation && <div className="mentor-response"><div className="mentor-response-head"><Sparkles size={14}/><strong>Selected output explained</strong><span>{explanation.source === 'offline' ? 'LOCAL' : 'AI'}</span></div><p>{explanation.explanation}</p><button className="btn btn-secondary btn-small" onClick={saveExplanation}><FileText size={13}/> Save explanation</button></div>}
        <div className="mentor-privacy"><ShieldCheck size={14}/><p><strong>Context stays minimal.</strong> No automatic terminal-history uploads. Review and confirm before selected output is shared with an AI endpoint.</p></div>
      </div></aside>}
      {rightCollapsed && <button className="restore-panel restore-panel--right" onClick={() => setRightCollapsed(false)} title="Show mentor panel"><ChevronLeftIcon/><span>MENTOR</span></button>}
    </div>
  </>;
}
function TargetIcon() { return <span className="target-icon"><Activity size={14}/></span>; }
function ChevronLeftIcon() { return <ChevronRight size={15} className="flip-x"/>; }

function NewNoteModal({ challenge, onClose, onSaved }: { challenge: Challenge | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const [title, setTitle] = useState(challenge ? `Notes: ${challenge.title}` : 'Untitled note'); const [content, setContent] = useState(''); const [tags, setTags] = useState(challenge?.tags.slice(0, 3).join(', ') ?? ''); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const save = async () => { if (!title.trim() || !content.trim()) { setError('Add a title and some notes before saving.'); return; } setBusy(true); setError(''); try { await api('/api/notes', { method: 'POST', body: JSON.stringify({ title: title.trim(), content, challenge_id: challenge?.id ?? null, tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean) }) }); await onSaved(); } catch (e) { setError(e instanceof Error ? e.message : 'Could not save this note.'); } finally { setBusy(false); } };
  return <Modal title="Save a notebook note" onClose={onClose}><div className="form-stack"><p className="form-help">This is your own note, saved separately from any AI explanation.</p><Field label="Title"><input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200}/></Field><Field label="Content"><textarea rows={7} value={content} onChange={(event) => setContent(event.target.value)} placeholder="What did you observe? Which command helped, and why?" maxLength={30000}/></Field><Field label="Tags (comma-separated)"><input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="linux, permissions, gotcha"/></Field>{error && <p className="field-error">{error}</p>}<div className="modal-actions"><button className="btn btn-secondary" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save note'} <Check size={14}/></button></div></div></Modal>;
}

function Notebook({ notes, challenges, onChanged, onNotice }: { notes: Note[]; challenges: Challenge[]; onChanged: () => Promise<void>; onNotice: (tone: Notice['tone'], message: string) => void }) {
  const [query, setQuery] = useState(''); const [kind, setKind] = useState('all'); const [selectedId, setSelectedId] = useState<string | null>(null); const [editing, setEditing] = useState(false); const [draft, setDraft] = useState({ title: '', content: '', challenge_id: '', tags: '' }); const [busy, setBusy] = useState(false);
  const filtered = notes.filter((note) => (kind === 'all' || note.kind === kind) && (!query || `${note.title} ${note.content} ${note.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase())));
  const selected = filtered.find((note) => note.id === selectedId) ?? notes.find((note) => note.id === selectedId) ?? null;
  const newEntry = () => { setSelectedId(null); setEditing(true); setDraft({ title: '', content: '', challenge_id: '', tags: '' }); };
  const editEntry = (note: Note) => { setSelectedId(note.id); setEditing(true); setDraft({ title: note.title, content: note.content, challenge_id: note.challenge_id ?? '', tags: note.tags.join(', ') }); };
  const save = async () => {
    if (!draft.title.trim() || !draft.content.trim()) { onNotice('error', 'A notebook entry needs a title and content.'); return; }
    setBusy(true);
    try {
      const body = { title: draft.title.trim(), content: draft.content, challenge_id: draft.challenge_id || null, tags: draft.tags.split(',').map((tag) => tag.trim()).filter(Boolean) };
      const path = selectedId ? `/api/notes/${selectedId}` : '/api/notes';
      const result = await api<Note>(path, { method: selectedId ? 'PUT' : 'POST', body: JSON.stringify(body) });
      await onChanged(); setSelectedId(result.id); setEditing(false); onNotice('success', 'Notebook entry saved locally.');
    } catch (e) { onNotice('error', e instanceof Error ? e.message : 'Could not save entry.'); }
    finally { setBusy(false); }
  };
  const remove = async (note: Note) => {
    if (!window.confirm(`Delete “${note.title}”? This cannot be undone.`)) return;
    try { await api(`/api/notes/${note.id}`, { method: 'DELETE' }); await onChanged(); setSelectedId(null); setEditing(false); onNotice('success', 'Notebook entry deleted.'); }
    catch (e) { onNotice('error', e instanceof Error ? e.message : 'Could not delete entry.'); }
  };
  return <><PageIntro eyebrow="PERSONAL KNOWLEDGE BASE" title="Knowledge notebook" subtitle="Keep your own discoveries and saved explanations as separate records. Everything here stays in your local app database." trailing={<button className="btn btn-primary" onClick={newEntry}><Plus size={15}/> New entry</button>}/>
    <div className="notebook-layout"><aside className="notebook-list-panel"><div className="notebook-list-head"><strong>YOUR ENTRIES <span>{filtered.length}</span></strong><div className="search-field search-field--compact"><Search size={14}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search notes…" aria-label="Search notebook"/></div><div className="note-filters"><button className={kind === 'all' ? 'filter-chip filter-chip--active' : 'filter-chip'} onClick={() => setKind('all')}>All</button><button className={kind === 'note' ? 'filter-chip filter-chip--active' : 'filter-chip'} onClick={() => setKind('note')}>My notes</button><button className={kind === 'explanation' ? 'filter-chip filter-chip--active' : 'filter-chip'} onClick={() => setKind('explanation')}>Explanations</button></div></div>
      <div className="note-list">{filtered.length ? filtered.map((note) => <button key={note.id} className={`note-list-item ${selected?.id === note.id ? 'note-list-item--active' : ''}`} onClick={() => { setSelectedId(note.id); setEditing(false); }}><span className={`note-kind-icon ${note.kind === 'explanation' ? 'note-kind-icon--explanation' : ''}`}>{note.kind === 'explanation' ? <Sparkles size={15}/> : <FileText size={15}/>}</span><span><strong>{note.title}</strong><small>{note.kind === 'explanation' ? 'Saved explanation' : 'Personal note'} · {new Date(note.updated_at).toLocaleDateString()}</small><p>{note.content.slice(0, 95).replace(/\n/g, ' ')}</p></span></button>) : <div className="notes-empty"><BookOpen size={21}/><strong>No entries found</strong><p>Create your first note or try another search.</p><button className="btn btn-secondary btn-small" onClick={newEntry}>Create note</button></div>}</div>
    </aside><section className="notebook-editor-panel">{editing ? <><div className="editor-panel-head"><div><div className="eyebrow">{selectedId ? 'EDIT ENTRY' : 'NEW ENTRY'}</div><h2>{draft.title || 'Untitled note'}</h2></div><button className="icon-button" onClick={() => setEditing(false)} title="Cancel editing"><X size={15}/></button></div><div className="form-stack"><Field label="Title"><input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} maxLength={200}/></Field><Field label="Content"><textarea className="note-content-editor" value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} rows={14} maxLength={30000} placeholder="Capture what you learned and how you verified it."/></Field><div className="form-row"><Field label="Related challenge"><select value={draft.challenge_id} onChange={(event) => setDraft({ ...draft, challenge_id: event.target.value })}><option value="">None</option>{challenges.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}</select></Field><Field label="Tags"><input value={draft.tags} onChange={(event) => setDraft({ ...draft, tags: event.target.value })} placeholder="linux, notes"/></Field></div><div className="modal-actions"><button className="btn btn-secondary" onClick={() => setEditing(false)}>Cancel</button><button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save changes'} <Check size={14}/></button></div></div></> : selected ? <><div className="editor-panel-head"><div><div className="eyebrow">{selected.kind === 'explanation' ? 'SAVED EXPLANATION' : 'PERSONAL NOTE'} / {selected.challenge_id ?? 'GENERAL'}</div><h2>{selected.title}</h2><div className="note-meta">Updated {new Date(selected.updated_at).toLocaleString()} · {selected.content.length.toLocaleString()} characters</div></div><div className="icon-actions"><button className="icon-button" onClick={() => editEntry(selected)} title="Edit entry"><Wrench size={15}/></button><button className="icon-button icon-button--danger" onClick={() => void remove(selected)} title="Delete entry"><Trash2 size={15}/></button></div></div><div className="note-content-preview">{selected.content}</div><div className="tag-list note-tags">{selected.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><button className="btn btn-secondary" onClick={() => editEntry(selected)}><Wrench size={14}/> Edit entry</button></> : <div className="notebook-welcome"><div className="notebook-big-icon"><BookOpen size={24}/></div><h2>A memory that belongs to you.</h2><p>Keep commands you understood, mistakes that taught you something, and saved explanations. Your notes are not automatically included in AI requests.</p><button className="btn btn-primary" onClick={newEntry}><Plus size={15}/> Create your first note</button></div>}</section></div>
  </>;
}

function Field({ label, children, help }: { label: string; children: ReactNode; help?: string }) { return <label className="field"><span>{label}</span>{children}{help && <small>{help}</small>}</label>; }

function Builder({ onNotice, onRefresh }: { onNotice: (tone: Notice['tone'], message: string) => void; onRefresh: () => Promise<void> }) {
  const [items, setItems] = useState<Record<string, any>[]>([]); const [selectedId, setSelectedId] = useState<string | null>(null); const [draft, setDraft] = useState<Record<string, any>>({}); const [isNew, setIsNew] = useState(false); const [busy, setBusy] = useState(false);
  const [newId, setNewId] = useState('my-first-lab'); const [seedJson, setSeedJson] = useState('{\n  "README.txt": "Your challenge notes go here.\\n"\n}');
  const load = useCallback(async (select?: string | null) => {
    try { const response = await api<{ items: Record<string, any>[] }>('/api/builder'); setItems(response.items); const target = select !== undefined ? response.items.find((item) => item.id === select) : response.items.find((item) => item.id === selectedId); if (target) choose(target); else if (!response.items.length) setDraft({}); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not load challenges.'); }
  }, [onNotice, selectedId]);
  useEffect(() => { void load(); }, []);
  const choose = (manifest: Record<string, any>) => {
    setSelectedId(manifest.id); setIsNew(false);
    setDraft({ ...manifest, hint1: manifest.offline_hints?.[0]?.content ?? '', hint2: manifest.offline_hints?.[1]?.content ?? '', hint3: manifest.offline_hints?.[2]?.content ?? '', validationType: manifest.validation?.type ?? 'text_lines', validationPath: manifest.validation?.path ?? 'evidence.txt', validationLines: (manifest.validation?.required_lines ?? ['complete']).join('\n'), validationContent: manifest.validation?.content ?? '', validationExpected: JSON.stringify(manifest.validation?.expected ?? {}, null, 2), validationMode: manifest.validation?.mode ?? '640', objectivesText: (manifest.learning_objectives ?? []).join('\n'), prerequisitesText: (manifest.prerequisites ?? []).join(', '), tagsText: (manifest.tags ?? []).join(', '), seedText: JSON.stringify(manifest.workspace_seed ?? {}, null, 2) });
  };
  const createNew = () => { setSelectedId(null); setIsNew(true); setNewId('my-first-lab'); setSeedJson('{\n  "README.txt": "Your challenge notes go here.\\n"\n}'); setDraft({ title: 'My first custom mission', track: 'Linux & Bash', difficulty: 'Beginner', summary: 'A short custom learning task.', description: 'Describe what the learner should investigate and why.', estimated_minutes: 15, completion_explanation: 'Review the actual artifact and explain why the result matters.', hint1: 'Think about the goal before choosing a command.', hint2: 'Inspect the supplied files and expected output.', hint3: 'Use the mission guide to create and verify the required evidence.', validationType: 'text_lines', validationPath: 'evidence.txt', validationLines: 'complete', validationContent: '', validationExpected: '{}', validationMode: '640', objectivesText: 'Investigate the provided starter files\nCreate a verifiable evidence artifact', prerequisitesText: '', tagsText: 'custom, practice' }); };
  const val = (key: string, value: unknown) => setDraft((current) => ({ ...current, [key]: value }));
  const manifestFromDraft = () => {
    const validationType = draft.validationType ?? draft.validation?.type ?? 'text_lines';
    let validation: Record<string, unknown>;
    if (validationType === 'exact_file') validation = { type: 'exact_file', path: String(draft.validationPath || 'result.txt'), content: String(draft.validationContent ?? '') };
    else if (validationType === 'json_subset') validation = { type: 'json_subset', path: String(draft.validationPath || 'report.json'), expected: JSON.parse(String(draft.validationExpected || '{}')) };
    else if (validationType === 'file_mode') validation = { type: 'file_mode', path: String(draft.validationPath || 'file.txt'), mode: String(draft.validationMode || '640'), owner: 'redpanda' };
    else if (validationType === 'process_stopped' && !isNew) validation = { type: 'process_stopped', pid_file: String(draft.validationPath || '.heartbeat.pid') };
    else validation = { type: 'text_lines', path: String(draft.validationPath || 'evidence.txt'), required_lines: String(draft.validationLines ?? 'complete').split('\n').map((line: string) => line.trim()).filter(Boolean) };
    const hints = [1, 2, 3].map((level) => ({ level, title: ['Think about the concept', 'Investigate this area', 'Guided route'][level - 1], content: String(draft[`hint${level}`] ?? '').trim() })).filter((hint) => hint.content);
    const base: Record<string, any> = {
      schema_version: 1, id: isNew ? `custom-${newId.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}` : selectedId,
      version: draft.version ?? '1.0.0', title: String(draft.title ?? '').trim(), track: String(draft.track ?? 'Custom').trim(), difficulty: draft.difficulty,
      summary: String(draft.summary ?? '').trim(), description: String(draft.description ?? '').trim(),
      learning_objectives: String(draft.objectivesText ?? (draft.learning_objectives ?? []).join('\n')).split('\n').map((line: string) => line.trim()).filter(Boolean),
      prerequisites: String(draft.prerequisitesText ?? (draft.prerequisites ?? []).join(', ')).split(',').map((line: string) => line.trim()).filter(Boolean),
      tags: String(draft.tagsText ?? (draft.tags ?? []).join(', ')).split(',').map((line: string) => line.trim()).filter(Boolean),
      environment_profile: draft.environment_profile ?? 'linux-basic', workspace_seed: isNew ? JSON.parse(seedJson) : JSON.parse(String(draft.seedText ?? '{}')),
      offline_hints: hints, validation, reset_policy: draft.reset_policy ?? 'reset-workspace-volume',
      completion_explanation: String(draft.completion_explanation ?? '').trim(), optional_extensions: draft.optional_extensions ?? [],
      network_requirements: draft.network_requirements ?? { mode: 'none', internet_access: false, description: 'No network interface is required for this mission.' },
      estimated_minutes: Number(draft.estimated_minutes ?? 15),
    };
    return base;
  };
  const save = async () => {
    setBusy(true);
    try {
      const manifest = manifestFromDraft();
      if (!manifest.title || !manifest.summary || !manifest.description || !manifest.learning_objectives.length || manifest.offline_hints.length !== 3) throw new Error('Add a title, summary, description, at least one objective, and all three offline hints.');
      if (isNew) {
        const result = await api<{ manifest: Record<string, any> }>('/api/builder', { method: 'POST', body: JSON.stringify({ manifest }) });
        onNotice('success', `Created ${result.manifest.title}. Custom scripts are intentionally disabled in this release.`); await load(result.manifest.id);
      } else if (selectedId) {
        const allowed = { title: manifest.title, track: manifest.track, difficulty: manifest.difficulty, summary: manifest.summary, description: manifest.description, learning_objectives: manifest.learning_objectives, prerequisites: manifest.prerequisites, tags: manifest.tags, offline_hints: manifest.offline_hints, validation: manifest.validation, completion_explanation: manifest.completion_explanation, estimated_minutes: manifest.estimated_minutes, ...(selectedId.startsWith('custom-') ? { workspace_seed: manifest.workspace_seed } : {}) };
        await api(`/api/builder/${selectedId}`, { method: 'PUT', body: JSON.stringify(allowed) }); onNotice('success', 'Challenge metadata saved. The built-in packaged definition remains unchanged.'); await load(selectedId);
      }
      await onRefresh();
    } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Challenge could not be saved. Check the manifest fields.'); }
    finally { setBusy(false); }
  };
  const disable = async () => {
    if (!selectedId || isNew) return;
    const typed = window.prompt(`Disable ${selectedId} from the catalogue? Existing notes and history remain. Type ${selectedId} to confirm.`);
    if (typed !== selectedId) return;
    try { await api(`/api/builder/${selectedId}/disable`, { method: 'POST', body: JSON.stringify({ confirmation: typed }) }); onNotice('success', 'Challenge disabled.'); await load(selectedId); await onRefresh(); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Challenge could not be disabled.'); }
  };
  const restore = async () => {
    if (!selectedId) return;
    if (!window.confirm(`Restore the packaged defaults for ${selectedId}? Your original built-in definition is preserved, but this removes your metadata override.`)) return;
    try { await api(`/api/builder/${selectedId}`, { method: 'DELETE' }); onNotice('success', 'Built-in challenge metadata restored to defaults.'); await load(selectedId); await onRefresh(); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Defaults could not be restored.'); }
  };
  const exportPack = async () => { if (!selectedId) return; try { await download(`/api/packs/${selectedId}/export`, `${selectedId}-pack.zip`); onNotice('success', 'Challenge pack exported. It contains no workspace data or secrets.'); } catch (e) { onNotice('error', e instanceof Error ? e.message : 'Export failed.'); } };
  const importPack = async (file?: File) => {
    if (!file) return;
    try {
      const inspect = await api<{ manifest: Record<string, any> }>('/api/packs/inspect', { method: 'POST', headers: { 'Content-Type': 'application/zip' }, body: file });
      const manifest = inspect.manifest;
      const ok = window.confirm(`Import challenge “${manifest.title}”?\n\nID: ${manifest.id}\nTrack: ${manifest.track}\nScripts: none executed\n\nContinue?`);
      if (!ok) return;
      const result = await api<{ challenge_id: string }>('/api/packs/import', { method: 'POST', headers: { 'Content-Type': 'application/zip' }, body: file });
      onNotice('success', `Imported ${result.challenge_id}.`); await load(result.challenge_id); await onRefresh();
    } catch (e) { onNotice('error', e instanceof Error ? e.message : 'Challenge pack import failed.'); }
  };
  const isCustom = isNew || Boolean(selectedId?.startsWith('custom-'));
  return <><PageIntro eyebrow="AUTHORING WORKBENCH" title="Challenge Builder" subtitle="Create and edit versioned mission manifests. Supported declarative validators are safe to inspect; imported scripts are not executed in this release." trailing={<div className="heading-actions"><label className="btn btn-secondary" htmlFor="pack-import"><Upload size={14}/> Import pack<input id="pack-import" className="visually-hidden" type="file" accept=".zip,application/zip" onChange={(event) => { void importPack(event.target.files?.[0]); event.currentTarget.value = ''; }}/></label><button className="btn btn-primary" onClick={createNew}><Plus size={15}/> New challenge</button></div>}/>
    <div className="builder-layout"><aside className="builder-catalog content-card"><div className="builder-catalog-head"><strong>MANIFESTS <span>{items.length}</span></strong><span className="catalog-live-dot"/></div><div className="builder-manifest-list">{items.map((item) => <button key={item.id} className={`builder-manifest-item ${selectedId === item.id && !isNew ? 'builder-manifest-item--active' : ''}`} onClick={() => choose(item)}><span className={`builder-manifest-icon ${item.is_custom ? 'builder-manifest-icon--custom' : ''}`}>{item.is_custom ? <Code2 size={15}/> : <FileCode2 size={15}/>}</span><span><strong>{item.title}</strong><small>{item.id} · v{item.version}</small></span>{item.disabled ? <span className="disabled-tag">OFF</span> : <ChevronRight size={14}/>}</button>)}<div className="builder-catalog-foot"><p>Built-in definitions are packaged separately from user overrides. Restore defaults never rewrites the bundled source files.</p><label className="btn btn-secondary btn-block" htmlFor="pack-import-lower"><Upload size={14}/> Import challenge pack<input id="pack-import-lower" className="visually-hidden" type="file" accept=".zip,application/zip" onChange={(event) => { void importPack(event.target.files?.[0]); event.currentTarget.value = ''; }}/></label></div></div></aside>
      <section className="builder-editor content-card"><div className="builder-editor-top"><div><div className="eyebrow">{isNew ? 'NEW CUSTOM MANIFEST' : `MANIFEST / ${selectedId ?? 'NO SELECTION'}`}</div><h2>{isNew ? 'Create challenge' : draft.title ?? 'Select a challenge'}</h2></div>{selectedId && !isNew && <span className={`builder-type-tag ${selectedId.startsWith('custom-') ? 'builder-type-tag--custom' : ''}`}>{selectedId.startsWith('custom-') ? 'CUSTOM' : 'BUILT IN'}</span>}</div>
      {!isNew && !selectedId ? <EmptyState title="Choose a manifest" body="Select a built-in mission on the left, or create a new custom challenge." action="Create challenge" onAction={createNew}/> : <><div className="builder-fields"><div className="builder-section-title"><span>01</span><strong>Mission metadata</strong><small>Identity and learning objective</small></div>{isNew && <Field label="Custom ID (lowercase, hyphens)"><input value={newId} onChange={(event) => setNewId(event.target.value)} placeholder="my-first-lab"/></Field>}<Field label="Mission title"><input value={draft.title ?? ''} onChange={(event) => val('title', event.target.value)} maxLength={120}/></Field><div className="form-row"><Field label="Learning track"><select value={draft.track ?? 'Linux & Bash'} onChange={(event) => val('track', event.target.value)}>{['Linux & Bash','Python','Networking','Web Security','Security Fundamentals','Integrated Capstone','Custom'].map((item) => <option key={item}>{item}</option>)}</select></Field><Field label="Difficulty"><select value={draft.difficulty ?? 'Beginner'} onChange={(event) => val('difficulty', event.target.value)}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></Field><Field label="Estimated minutes"><input type="number" min={1} max={600} value={draft.estimated_minutes ?? 15} onChange={(event) => val('estimated_minutes', Number(event.target.value))}/></Field></div><Field label="Short summary"><input value={draft.summary ?? ''} onChange={(event) => val('summary', event.target.value)} maxLength={240}/></Field><Field label="Mission description"><textarea rows={4} value={draft.description ?? ''} onChange={(event) => val('description', event.target.value)} maxLength={6000}/></Field><Field label="Learning objectives (one per line)"><textarea rows={3} value={draft.objectivesText ?? ''} onChange={(event) => val('objectivesText', event.target.value)}/></Field><Field label="Prerequisite IDs (comma-separated)"><input value={draft.prerequisitesText ?? ''} onChange={(event) => val('prerequisitesText', event.target.value)} placeholder="challenge-01, custom-first-lab"/></Field><Field label="Tags (comma-separated)"><input value={draft.tagsText ?? ''} onChange={(event) => val('tagsText', event.target.value)}/></Field>
      {isCustom && <><Field label="Starter files as a JSON object of workspace-relative paths and UTF-8 text" help="Paths are validated to stay inside this isolated workspace. File content limit: 2 MiB total."><textarea rows={5} value={isNew ? seedJson : draft.seedText ?? '{}'} onChange={(event) => isNew ? setSeedJson(event.target.value) : val('seedText', event.target.value)} className="code-editor-input"/></Field></>}
      <div className="builder-section-title"><span>02</span><strong>Progressive offline hints</strong><small>All three levels are required</small></div>{[1,2,3].map((level) => <Field key={level} label={`Hint level ${level}${level === 1 ? ' · conceptual' : level === 2 ? ' · investigative' : ' · detailed'}`}><textarea rows={2} value={draft[`hint${level}`] ?? ''} onChange={(event) => val(`hint${level}`, event.target.value)} maxLength={6000}/></Field>)}
      <div className="builder-section-title"><span>03</span><strong>Completion validator</strong><small>State-based and declarative</small></div><Field label="Validator type"><select value={draft.validationType ?? draft.validation?.type ?? 'text_lines'} onChange={(event) => val('validationType', event.target.value)}>{['text_lines','exact_file','json_subset','file_mode', ...(!isNew && !isCustom && draft.validation?.type === 'process_stopped' ? ['process_stopped'] : [])].map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></Field><Field label="Workspace-relative path"><input value={draft.validationPath ?? draft.validation?.path ?? draft.validation?.pid_file ?? 'evidence.txt'} onChange={(event) => val('validationPath', event.target.value)}/></Field>{(draft.validationType ?? draft.validation?.type) === 'text_lines' || !(draft.validationType ?? draft.validation?.type) ? <Field label="Required lines (one per line)"><textarea rows={3} value={draft.validationLines ?? ''} onChange={(event) => val('validationLines', event.target.value)}/></Field> : null}{(draft.validationType ?? draft.validation?.type) === 'exact_file' && <Field label="Expected exact UTF-8 file content"><textarea rows={5} className="code-editor-input" value={draft.validationContent ?? ''} onChange={(event) => val('validationContent', event.target.value)}/></Field>}{(draft.validationType ?? draft.validation?.type) === 'json_subset' && <Field label="Expected JSON fields"><textarea rows={5} className="code-editor-input" value={draft.validationExpected ?? '{}'} onChange={(event) => val('validationExpected', event.target.value)}/></Field>}{(draft.validationType ?? draft.validation?.type) === 'file_mode' && <Field label="Required octal permission mode"><input value={draft.validationMode ?? '640'} onChange={(event) => val('validationMode', event.target.value)} maxLength={4}/></Field>}
      <Field label="Completion explanation (shown after validation)"><textarea rows={3} value={draft.completion_explanation ?? ''} onChange={(event) => val('completion_explanation', event.target.value)} maxLength={6000}/></Field>
      <div className="builder-section-title"><span>04</span><strong>Manifest portability</strong><small>Export and share safely</small></div><div className="callout-row callout-row--compact"><ShieldCheck size={16}/><p>Challenge packs contain only the manifest and allowed text seed files. This build does not execute custom scripts, import Dockerfiles, or let a manifest select container privileges or network settings.</p></div>
      <div className="builder-save-row"><div>{selectedId && !isNew && !selectedId.startsWith('custom-') && <button className="btn btn-secondary" onClick={() => void restore()}><RotateCcw size={14}/> Restore built-in defaults</button>}{selectedId && !isNew && <button className="btn btn-secondary" onClick={() => void exportPack()}><ArrowDownToLine size={14}/> Export pack</button>}{selectedId && !isNew && <button className="btn btn-danger-ghost" onClick={() => void disable()}><LockKeyhole size={14}/> Disable</button>}</div><button className="btn btn-primary" onClick={() => void save()} disabled={busy}>{busy ? 'Saving…' : isNew ? 'Create challenge' : 'Save manifest'} <Check size={14}/></button></div>
      </div></>}
      </section></div>
  </>;
}

function SettingsPage({ diagnostics, onNotice, onRefresh }: { diagnostics: Diagnostic | null; onNotice: (tone: Notice['tone'], message: string) => void; onRefresh: () => Promise<void> }) {
  const [aiSettings, setAiSettings] = useState({ configured: false, provider: 'OpenAI-compatible', base_url: 'https://api.example.com/v1', model: '', api_key_saved: false, timeout_seconds: 20, warning: '' });
  const [apiKey, setApiKey] = useState(''); const [aiBusy, setAiBusy] = useState(false); const [dataMode, setDataMode] = useState<'merge' | 'replace'>('merge'); const [workspaceId, setWorkspaceId] = useState('challenge-01'); const [restoreBusy, setRestoreBusy] = useState(false);
  const loadAI = async () => { try { const result = await api<typeof aiSettings>('/api/ai/settings'); setAiSettings({ ...aiSettings, ...result }); } catch { /* diagnostics remains useful even when AI config is unreadable */ } };
  useEffect(() => { void loadAI(); }, []);
  const saveAI = async () => { setAiBusy(true); try { const result = await api<typeof aiSettings>('/api/ai/settings', { method: 'PUT', body: JSON.stringify({ provider: aiSettings.provider, base_url: aiSettings.base_url, model: aiSettings.model, api_key: apiKey, timeout_seconds: aiSettings.timeout_seconds }) }); setAiSettings({ ...aiSettings, ...result }); setApiKey(''); onNotice('success', 'AI settings saved to your private local configuration file.'); } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not save AI settings.'); } finally { setAiBusy(false); } };
  const testAI = async () => { setAiBusy(true); try { const result = await api<{ connected: boolean; message: string; sample: string }>('/api/ai/test', { method: 'POST' }); onNotice('success', `${result.message} Response: ${result.sample}`); } catch (error) { onNotice('error', error instanceof Error ? error.message : 'AI connection test failed.'); } finally { setAiBusy(false); } };
  const clearAI = async () => { if (!window.confirm('Delete the saved AI configuration and credential file? Offline hints and the notebook will continue to work.')) return; try { await api('/api/ai/settings', { method: 'DELETE' }); await loadAI(); setApiKey(''); onNotice('success', 'Saved AI configuration deleted.'); } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not delete AI configuration.'); } };
  const exportData = async () => { try { await download('/api/data/export', 'redpanda-progress-export.json'); onNotice('success', 'Progress and notebook export downloaded. It does not contain API keys or workspace files.'); } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Export failed.'); } };
  const restoreData = async (file?: File) => {
    if (!file) return;
    setRestoreBusy(true);
    try {
      const imported = JSON.parse(await file.text()) as Record<string, unknown>;
      const preview = await api<{ valid: boolean; counts: Record<string, number>; preference_count: number; warning: string }>('/api/data/preview', { method: 'POST', body: JSON.stringify({ data: imported }) });
      const summary = `Import preview\n\nProgress: ${preview.counts.progress}\nNotebook entries: ${preview.counts.notes}\nAchievements: ${preview.counts.achievements}\nCompletion history records: ${preview.counts.completion_history}\nPreferences: ${preview.preference_count}\n\n${preview.warning}\n\nContinue with ${dataMode.toUpperCase()} mode?`;
      if (!window.confirm(summary)) return;
      const confirmation = window.prompt('Type RESTORE DATA exactly to confirm.');
      if (confirmation !== 'RESTORE DATA') return;
      await api('/api/data/restore', { method: 'POST', body: JSON.stringify({ data: imported, mode: dataMode, confirmation }) });
      onNotice('success', 'Data restored. Existing workspace files and AI credentials were not imported or overwritten.'); await onRefresh();
    } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Import failed. Check that this is a RedPanda Labs export.'); }
    finally { setRestoreBusy(false); }
  };
  const resetProgress = async () => {
    if (!window.confirm('Reset all current challenge progress? This preserves notes, saved explanations, workspace contents, completion history, and historical achievements.')) return;
    const confirmation = window.prompt('Type RESET ALL LEARNING PROGRESS exactly.'); if (confirmation !== 'RESET ALL LEARNING PROGRESS') return;
    try { await api('/api/progress/reset', { method: 'POST', body: JSON.stringify({ confirmation }) }); onNotice('success', 'Current progress cleared. Workspaces and notebook entries remain.'); await onRefresh(); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Could not reset progress.'); }
  };
  const deleteData = async () => {
    const confirmation = window.prompt('This removes local progress, notes, saved explanations, achievements, overrides, saved AI credentials, and verified RedPanda-managed workspaces. Source code and built-in challenge definitions remain. Type DELETE REDPANDA DATA exactly.');
    if (confirmation !== 'DELETE REDPANDA DATA') return;
    try { await api('/api/data/delete', { method: 'POST', body: JSON.stringify({ confirmation }) }); onNotice('success', 'Application data deleted. Built-in challenge files remain intact.'); await loadAI(); await onRefresh(); }
    catch (error) { onNotice('error', error instanceof Error ? error.message : 'Application data could not be deleted safely.'); }
  };
  const exportWorkspace = async () => { const confirmation = window.prompt(`The archive contains files only from ${workspaceId}'s registered workspace. Type ${workspaceId} to export it.`); if (confirmation !== workspaceId) return; try { await download(`/api/workspaces/${workspaceId}/archive`, `${workspaceId}-workspace.tar`, { method: 'POST', body: JSON.stringify({ confirmation }) }); onNotice('success', 'Selected workspace archive exported.'); } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Workspace export failed.'); } };
  const restoreWorkspace = async (file?: File) => { if (!file) return; const confirmation = window.prompt(`This will merge files from the selected archive into ${workspaceId}. Existing files with the same paths may be replaced. Type ${workspaceId} to confirm.`); if (confirmation !== workspaceId) return; try { await api(`/api/workspaces/${workspaceId}/archive`, { method: 'PUT', headers: { 'Content-Type': 'application/x-tar', 'X-Confirm-Workspace': workspaceId }, body: file }); onNotice('success', 'Workspace archive restored.'); await onRefresh(); } catch (error) { onNotice('error', error instanceof Error ? error.message : 'Workspace restore failed.'); } };
  const copyGitCommands = () => {
    const commands = 'git status --short\ngit remote -v\ngit add .\ngit commit -m "Build RedPanda Labs local learning platform"\ngit push -u origin main';
    void navigator.clipboard?.writeText(commands).then(() => onNotice('success', 'Git inspection and push commands copied. Review the remote and staged files before running them.')).catch(() => onNotice('info', commands));
  };
  return <><PageIntro eyebrow="LOCAL CONFIGURATION" title="Settings & Lab Manager" subtitle="Inspect readiness, configure optional AI, manage backups, and control what gets reset or deleted." trailing={<button className="btn btn-secondary" onClick={() => void onRefresh()}><RefreshCw size={14}/> Refresh checks</button>}/>
    <div className="settings-overview-grid"><div className="settings-overview-card"><span className="settings-overview-icon"><HardDrive size={17}/></span><div><small>DOCKER DAEMON</small><strong>{diagnostics?.docker.available ? 'Connected' : 'Unavailable'}</strong><p>{diagnostics?.docker.docker_version ?? 'The daemon has not responded'}</p></div><span className={`readiness-chip ${diagnostics?.docker.available ? 'readiness-chip--ready' : 'readiness-chip--warning'}`}>{diagnostics?.docker.available ? 'READY' : 'CHECK'}</span></div><div className="settings-overview-card"><span className="settings-overview-icon"><Database size={17}/></span><div><small>LOCAL DATABASE</small><strong>{diagnostics?.database.status === 'connected' ? 'Connected' : 'Checking'}</strong><p>SQLite · Alembic migrations</p></div><span className="readiness-chip readiness-chip--ready">LOCAL</span></div><div className="settings-overview-card"><span className="settings-overview-icon"><Bot size={17}/></span><div><small>AI MENTOR</small><strong>{aiSettings.configured ? 'Configured' : 'Offline mode'}</strong><p>{aiSettings.configured ? aiSettings.provider : 'No API key required'}</p></div><span className={`readiness-chip ${aiSettings.configured ? 'readiness-chip--ready' : ''}`}>{aiSettings.configured ? 'SET' : 'OPTIONAL'}</span></div></div>
    <div className="settings-layout"><div className="settings-main-column">
      <section className="content-card settings-card"><div className="settings-card-heading"><div className="settings-card-icon settings-card-icon--ai"><Bot size={18}/></div><div><h2>AI mentor configuration</h2><p>Optional OpenAI-compatible chat endpoint. Hosted and compatible local model APIs are supported.</p></div><span className="optional-pill">OPTIONAL</span></div>
        {aiSettings.warning && <div className="callout-row callout-row--warning"><Info size={15}/><p>{aiSettings.warning}</p></div>}
        <div className="form-stack"><div className="form-row"><Field label="Provider profile"><input value={aiSettings.provider} onChange={(event) => setAiSettings({ ...aiSettings, provider: event.target.value })}/></Field><Field label="Model name"><input value={aiSettings.model} onChange={(event) => setAiSettings({ ...aiSettings, model: event.target.value })} placeholder="model-name" /></Field></div><Field label="Base URL" help="Remote providers must use HTTPS. Local HTTP is allowed only for localhost endpoints."><input type="url" value={aiSettings.base_url} onChange={(event) => setAiSettings({ ...aiSettings, base_url: event.target.value })} placeholder="https://api.example.com/v1" autoComplete="url"/></Field><div className="form-row"><Field label={aiSettings.api_key_saved ? 'API key (leave blank to keep saved key)' : 'API key (stored in a private local file)'}><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={aiSettings.api_key_saved ? 'Saved · not shown' : 'Optional for local endpoints'} autoComplete="new-password"/></Field><Field label="Request timeout (seconds)"><select value={aiSettings.timeout_seconds} onChange={(event) => setAiSettings({ ...aiSettings, timeout_seconds: Number(event.target.value) })}>{[5,10,15,20,30,45,60,90,120].map((value) => <option value={value} key={value}>{value} seconds</option>)}</select></Field></div><div className="privacy-note"><KeyRound size={15}/><p>Credentials live in <code>~/.config/redpanda-labs/ai.json</code> with owner-only permissions. File permissions are not encryption. Keys are never saved to the project, database, notebook export, or challenge packs.</p></div><div className="settings-button-row"><button className="btn btn-primary" onClick={() => void saveAI()} disabled={aiBusy}>{aiBusy ? 'Saving…' : 'Save configuration'} <Check size={14}/></button><button className="btn btn-secondary" onClick={() => void testAI()} disabled={aiBusy || !aiSettings.configured}><Activity size={14}/> Test connection</button>{aiSettings.api_key_saved && <button className="btn btn-danger-ghost" onClick={() => void clearAI()} disabled={aiBusy}><Trash2 size={14}/> Delete AI config</button>}</div></div>
      </section>
      <section className="content-card settings-card"><div className="settings-card-heading"><div className="settings-card-icon"><Database size={18}/></div><div><h2>Progress & notebook backups</h2><p>Versioned data export. The export excludes secrets and challenge workspace files.</p></div></div><div className="backup-row"><div className="backup-symbol"><ArrowDownToLine size={17}/></div><div><strong>Export progress and notes</strong><p>Progress, mastery history, notebook entries, saved explanations, and supported preferences.</p></div><button className="btn btn-secondary btn-small" onClick={() => void exportData()}>Export JSON <ArrowDownToLine size={13}/></button></div><div className="backup-row"><div className="backup-symbol"><Upload size={17}/></div><div><strong>Restore a progress export</strong><p>Preview record counts, then merge or replace current progress and notebook content.</p><div className="restore-mode"><label><input type="radio" checked={dataMode === 'merge'} onChange={() => setDataMode('merge')}/> Merge</label><label><input type="radio" checked={dataMode === 'replace'} onChange={() => setDataMode('replace')}/> Replace</label></div></div><label className="btn btn-secondary btn-small">{restoreBusy ? 'Checking…' : 'Choose JSON'}<input className="visually-hidden" type="file" accept="application/json,.json" disabled={restoreBusy} onChange={(event) => { void restoreData(event.target.files?.[0]); event.currentTarget.value = ''; }}/></label></div><div className="backup-row"><div className="backup-symbol"><HardDrive size={17}/></div><div><strong>Workspace archive</strong><p>Back up one selected challenge's files separately from progress and notes.</p><div className="workspace-archive-picker"><label>Selected mission <select value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)}>{Array.from({ length: 15 }, (_, i) => `challenge-${String(i + 1).padStart(2, '0')}`).map((id) => <option key={id} value={id}>{id}</option>)}</select></label></div></div><div className="archive-actions"><button className="btn btn-secondary btn-small" onClick={() => void exportWorkspace()}>Export</button><label className="btn btn-secondary btn-small">Restore<input className="visually-hidden" type="file" accept=".tar,application/x-tar" onChange={(event) => { void restoreWorkspace(event.target.files?.[0]); event.currentTarget.value = ''; }}/></label></div></div></section>
      <section className="content-card settings-card"><div className="settings-card-heading"><div className="settings-card-icon settings-card-icon--git"><GitBranch size={18}/></div><div><h2>GitHub readiness</h2><p>Inspect your remote and review staged files before publishing. No token or Git configuration is changed automatically.</p></div></div><div className="git-command-block"><pre><code>git status --short{ '\n' }git remote -v{ '\n' }git add .{ '\n' }git commit -m "Build RedPanda Labs local learning platform"{ '\n' }git push -u origin main</code></pre><button className="btn btn-secondary btn-small" onClick={copyGitCommands}>Copy commands</button></div><p className="muted-text"><Info size={13}/> If your current branch is not <code>main</code>, replace it with the branch you intend to push. Never commit private data, local databases, `.env`, AI keys, or workspace archives.</p></section>
    </div><aside className="settings-side-column"><section className="content-card diagnostics-card"><div className="card-heading"><div><div className="eyebrow">PREFLIGHT REPORT</div><h3>Diagnostics</h3></div><Gauge size={17}/></div><div className="diagnostic-items"><DiagnosticItem label="Python runtime" value={diagnostics ? 'Available' : 'Checking'} good={Boolean(diagnostics)}/><DiagnosticItem label="Node.js" value={diagnostics?.frontend.node ?? 'Not found'} good={Boolean(diagnostics?.frontend.node)}/><DiagnosticItem label="npm" value={diagnostics?.frontend.npm ?? 'Not found'} good={Boolean(diagnostics?.frontend.npm)}/><DiagnosticItem label="Frontend build" value={diagnostics?.frontend.built ? 'Built' : 'Missing'} good={Boolean(diagnostics?.frontend.built)}/><DiagnosticItem label="Docker daemon" value={diagnostics?.docker.available ? 'Connected' : 'Unavailable'} good={Boolean(diagnostics?.docker.available)}/><DiagnosticItem label="Lab image" value={diagnostics?.docker.image_ready ? LAB_IMAGE : 'Missing'} good={Boolean(diagnostics?.docker.image_ready)}/><DiagnosticItem label="Database" value={diagnostics?.database.status ?? 'Checking'} good={diagnostics?.database.status === 'connected'}/><DiagnosticItem label="Free disk space" value={diagnostics ? formatBytes(diagnostics.storage.free_bytes) : '—'} good={Boolean(diagnostics && diagnostics.storage.free_bytes > 2 * 1024 ** 3)}/></div><div className={`release-readiness ${diagnostics?.release_ready ? 'release-readiness--ready' : ''}`}><Shield size={16}/><div><strong>{diagnostics?.release_ready ? 'Release checks passed' : 'Awaiting integration verification'}</strong><p>{diagnostics?.release_note ?? 'Run the test suite and review outstanding checks.'}</p></div></div><p className="settings-doc-link">For detailed command output, run <code>bash scripts/diagnostics.sh</code> from the project folder.</p></section>
      <section className="content-card reset-card"><div className="settings-card-heading"><div className="settings-card-icon settings-card-icon--warning"><RotateCcw size={18}/></div><div><h2>Reset & deletion</h2><p>These operations have different effects.</p></div></div><div className="reset-option"><div><strong>Reset all progress</strong><p>Clears current challenge states. Notes, history, and workspace files are preserved.</p></div><button className="btn btn-secondary btn-small" onClick={() => void resetProgress()}>Reset progress</button></div><div className="reset-option reset-option--danger"><div><strong>Delete application data</strong><p>Removes local learning records, saved AI config, overrides, and verified application-managed workspaces.</p></div><button className="btn btn-danger-ghost btn-small" onClick={() => void deleteData()}><Trash2 size={13}/> Delete data</button></div><div className="data-location"><Database size={14}/><div><strong>Local data location</strong><small>~/.local/share/redpanda-labs/</small><small>Config: ~/.config/redpanda-labs/</small><small>Cache: ~/.cache/redpanda-labs/</small></div></div></section></aside></div>
  </>;
}
function DiagnosticItem({ label, value, good }: { label: string; value: string; good: boolean }) { return <div className="diagnostic-item"><span className={`diagnostic-check ${good ? 'diagnostic-check--good' : ''}`}>{good ? <Check size={11}/> : <Clock3 size={11}/>}</span><span>{label}</span><strong>{value}</strong></div>; }
