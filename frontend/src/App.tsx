import { useEffect, useState, type FormEvent } from 'react'
import {
  Activity, ArrowRight, Bell, BookOpen, Check, CheckCircle2, Clock3,
  FileImage, HeartHandshake, Languages, Leaf, MapPin, Menu, Package,
  Plus, Search, ShieldCheck, Sparkles, Truck, Users, X,
} from 'lucide-react'
import './giftbridge.css'

type View = 'Overview' | 'Donate an item' | 'Needs registry' | 'Match review' | 'Volunteer tasks' | 'Impact & analytics' | 'Admin'
type Role = 'Donor' | 'Coordinator' | 'Volunteer' | 'Admin'
type Item = { id: string; title: string; category: string; condition: number; quantity: number; age: string; status: string }
type Need = { id: string; village: string; category: string; quantity: number; urgency: number; age: string; deadline: string; status: string }
type Match = { id: string; item: string; village: string; category: string; score: number; reason: string; status: string; rejection?: string }
type Task = { id: string; village: string; route: string; items: number; date: string; status: string }

const seedItems: Item[] = [
  { id: 'GB-2048', title: 'Children’s storybook set', category: 'Books', condition: 9, quantity: 12, age: 'Children', status: 'Approved' },
  { id: 'GB-2047', title: 'Warm woollen blankets', category: 'Blankets', condition: 8, quantity: 6, age: 'All ages', status: 'In review' },
  { id: 'GB-2046', title: 'Geometry boxes', category: 'Stationery', condition: 10, quantity: 18, age: 'Teens', status: 'Matched' },
]
const seedNeeds: Need[] = [
  { id: 'NE-118', village: 'Kandaghat cluster', category: 'Blankets', quantity: 24, urgency: 5, age: 'All ages', deadline: 'Nov 30', status: 'Open' },
  { id: 'NE-117', village: 'Chail school', category: 'Books', quantity: 30, urgency: 4, age: 'Children', deadline: 'Dec 08', status: 'Open' },
  { id: 'NE-116', village: 'Mashobra anganwadi', category: 'Clothes', quantity: 16, urgency: 3, age: 'Infant', deadline: 'Dec 12', status: 'Open' },
]
const seedMatches: Match[] = [
  { id: 'MA-381', item: 'Warm woollen blankets', village: 'Kandaghat cluster', category: 'Blankets', score: 94, reason: 'Same category · urgent winter need · quantity fits', status: 'Suggested' },
  { id: 'MA-380', item: 'Children’s storybook set', village: 'Chail school', category: 'Books', score: 88, reason: 'Age group fits · school term demand', status: 'Suggested' },
  { id: 'MA-379', item: 'Geometry boxes', village: 'Chail school', category: 'Stationery', score: 81, reason: 'Close category · nearby pickup route', status: 'Accepted' },
]
const seedTasks: Task[] = [
  { id: 'PK-052', village: 'Kandaghat cluster', route: 'Campus north gate → Kandaghat', items: 2, date: 'Today · 2:30 PM', status: 'Available' },
  { id: 'PK-051', village: 'Chail school', route: 'Hostel block B → Chail', items: 3, date: 'Tomorrow · 10:00 AM', status: 'Claimed' },
]

const navItems: { title: View; icon: typeof Activity; section: string }[] = [
  { title: 'Overview', icon: Activity, section: 'Workspace' },
  { title: 'Donate an item', icon: Package, section: 'Workspace' },
  { title: 'Needs registry', icon: BookOpen, section: 'Workspace' },
  { title: 'Match review', icon: HeartHandshake, section: 'Operations' },
  { title: 'Volunteer tasks', icon: Truck, section: 'Operations' },
  { title: 'Impact & analytics', icon: Activity, section: 'Insights' },
  { title: 'Admin', icon: ShieldCheck, section: 'Insights' },
]

function fromStorage<T,>(key: string, fallback: T): T {
  try { const value = localStorage.getItem(key); return value ? JSON.parse(value) as T : fallback }
  catch { return fallback }
}

function App() {
  const [view, setView] = useState<View>('Overview')
  const [role, setRole] = useState<Role>('Coordinator')
  const [language, setLanguage] = useState<'EN' | 'हिं'>('EN')
  const [menuOpen, setMenuOpen] = useState(false)
  const [items, setItems] = useState(() => fromStorage<Item[]>('giftbridge-items', seedItems))
  const [needs, setNeeds] = useState(() => fromStorage<Need[]>('giftbridge-needs', seedNeeds))
  const [matches, setMatches] = useState(() => fromStorage<Match[]>('giftbridge-matches', seedMatches))
  const [tasks, setTasks] = useState(() => fromStorage<Task[]>('giftbridge-tasks', seedTasks))
  const [toast, setToast] = useState('')

  useEffect(() => { localStorage.setItem('giftbridge-items', JSON.stringify(items)) }, [items])
  useEffect(() => { localStorage.setItem('giftbridge-needs', JSON.stringify(needs)) }, [needs])
  useEffect(() => { localStorage.setItem('giftbridge-matches', JSON.stringify(matches)) }, [matches])
  useEffect(() => { localStorage.setItem('giftbridge-tasks', JSON.stringify(tasks)) }, [tasks])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 2800); return () => window.clearTimeout(timer) }, [toast])

  const text = (value: string) => {
    if (language === 'EN') return value
    const translations: Record<string, string> = {
      'Overview': 'अवलोकन', 'Donate an item': 'वस्तु दान करें', 'Needs registry': 'ज़रूरतें', 'Match review': 'मिलान समीक्षा',
      'Volunteer tasks': 'स्वयंसेवक कार्य', 'Impact & analytics': 'प्रभाव और विश्लेषण', 'Admin': 'प्रशासन',
      'Good morning, Anshika': 'सुप्रभात, अंशिका', 'A community supply chain, made visible.': 'समुदाय की ज़रूरतें और सहयोग, अब एक जगह।',
      'New donation': 'नया दान', 'Open needs': 'खुली ज़रूरतें', 'Items matched': 'मिले हुए दान',
      'Confirmed deliveries': 'पुष्ट डिलीवरी', 'Waiting for review': 'समीक्षा बाकी',
    }
    return translations[value] ?? value
  }
  const navigate = (next: View) => { setView(next); setMenuOpen(false) }
  const saveItem = (item: Item) => { setItems((current) => [item, ...current]); setToast('Donation saved in this demo workspace.') }
  const saveNeed = (need: Need) => { setNeeds((current) => [need, ...current]); setToast('Need saved in this demo workspace.') }
  const updateMatch = (id: string, status: string, rejection?: string) => {
    setMatches((current) => current.map((match) => match.id === id ? { ...match, status, rejection } : match))
    setToast(status === 'Rejected' ? 'Match rejected with a recorded reason.' : `Match ${status.toLowerCase()}.`)
  }

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Leaf size={19} /></div><div><strong>CMP</strong><small>COLLEGE COMMUNITY</small></div></div>
      <div className="campus-select"><i />Himachal Campus<span>⌄</span></div>
      <nav className="nav-stack" aria-label="Main navigation">{['Workspace', 'Operations', 'Insights'].map((section) => <div className="nav-group" key={section}><p>{section}</p>{navItems.filter((item) => item.section === section).map(({ title, icon: Icon }) => <button key={title} className={`nav-link ${view === title ? 'active' : ''}`} onClick={() => navigate(title)}><Icon size={17} /><span>{text(title)}</span>{title === 'Match review' && <b>2</b>}</button>)}</div>)}</nav>
      <div className="sidebar-foot"><div className="bandwidth"><Activity size={15} /><span><b>Low-bandwidth mode</b><small>Text-first · images on demand</small></span><i /></div><div className="profile"><div className="avatar">AN</div><span><b>Anshika</b><small>College committee</small></span><button aria-label="Account menu">⌄</button></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><button className="icon-button mobile-menu" onClick={() => setMenuOpen((open) => !open)} aria-label="Toggle navigation"><Menu size={19} /></button><div className="breadcrumb"><span>CMP</span><i>/</i><b>{text(view)}</b></div><div className="top-actions"><label className="search-box"><Search size={15} /><input placeholder="Search items, villages…" aria-label="Search items and villages" /></label><button className="language-switch" onClick={() => setLanguage((current) => current === 'EN' ? 'हिं' : 'EN')} title="Switch language"><Languages size={16} /><span>{language}</span></button><button className="icon-button bell-button" aria-label="Notifications"><Bell size={18} /><i /></button><label className="role-picker"><span>View as</span><select value={role} onChange={(event) => setRole(event.target.value as Role)} aria-label="Demo role"><option>Donor</option><option>Coordinator</option><option>Volunteer</option><option>Admin</option></select></label></div></header>
      <div className="demo-ribbon"><Sparkles size={14} /><b>DEMO WORKSPACE</b><span>Sample records only. Role switching simulates workflows; sign-in and permissions are not connected yet.</span></div>
      <div className="page-content">
        {view === 'Overview' && <Overview items={items} needs={needs} matches={matches} navigate={navigate} text={text} />}
        {view === 'Donate an item' && <Donate onSave={saveItem} />}
        {view === 'Needs registry' && <Needs needs={needs} onSave={saveNeed} />}
        {view === 'Match review' && <MatchDesk matches={matches} onUpdate={updateMatch} />}
        {view === 'Volunteer tasks' && <Tasks tasks={tasks} setTasks={setTasks} setToast={setToast} />}
        {view === 'Impact & analytics' && <Analytics items={items} needs={needs} matches={matches} />}
        {view === 'Admin' && <Admin items={items} setItems={setItems} setToast={setToast} />}
      </div>
    </main>
    {toast && <div className="toast" role="status"><CheckCircle2 size={17} />{toast}<button onClick={() => setToast('')} aria-label="Dismiss"><X size={15} /></button></div>}
  </div>
}

function Heading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="description">{description}</p></div>{action}</div>
}
function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) { return <section className={`panel ${className}`}>{children}</section> }
function PanelTitle({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) { return <div className="panel-title"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>{action}</div> }
function Stat({ label, value, note, icon: Icon }: { label: string; value: string; note: string; icon: typeof Activity }) { return <div className="stat-card"><div className="stat-head"><span>{label}</span><Icon size={17} /></div><strong>{value}</strong><small>{note}</small></div> }
function Status({ value }: { value: string }) { const kind = ['Approved', 'Accepted', 'Confirmed', 'Claimed', 'Delivered'].includes(value) ? 'good' : value === 'Rejected' ? 'bad' : 'wait'; return <span className={`status ${kind}`}><i />{value}</span> }

function Overview({ items, needs, matches, navigate, text }: { items: Item[]; needs: Need[]; matches: Match[]; navigate: (view: View) => void; text: (value: string) => string }) {
  return <><Heading eyebrow="MONDAY, NOVEMBER 23, 2026" title={text('Good morning, Anshika')} description={text('A community supply chain, made visible.')} action={<button className="primary-button" onClick={() => navigate('Donate an item')}><Plus size={16} />{text('New donation')}</button>} />
    <div className="stats"><Stat label={text('Open needs')} value={`${needs.filter((need) => need.status === 'Open').length + 18}`} note="Across nearby villages · sample" icon={BookOpen} /><Stat label={text('Items matched')} value="86" note="This semester · sample" icon={HeartHandshake} /><Stat label={text('Confirmed deliveries')} value="62" note="Recipient-confirmed · sample" icon={CheckCircle2} /><Stat label={text('Waiting for review')} value={`${matches.filter((match) => match.status === 'Suggested').length + 3}`} note="Matches and listings" icon={Clock3} /></div>
    <div className="columns"><Panel><PanelTitle eyebrow="SUPPLY & NEEDS" title="Where support is needed" action={<button className="text-button" onClick={() => navigate('Needs registry')}>View needs <ArrowRight size={14} /></button>} /><p className="panel-note">A sample snapshot of approved goods and current requests.</p><div className="supply-bars">{[['Blankets', 36, 76], ['Books', 68, 51], ['Clothes', 53, 65], ['Stationery', 72, 47]].map(([label, supply, demand]) => <div className="supply-row" key={String(label)}><span>{label}</span><div><i style={{ width: `${supply}%` }} /><b style={{ width: `${demand}%` }} /></div><small>{Number(demand) > Number(supply) ? 'Gap' : 'Ready'}</small></div>)}</div><div className="legend"><span><i className="green-dot" />Approved supply</span><span><i className="gold-dot" />Open requests</span><small>Illustrative</small></div></Panel>
      <Panel><PanelTitle eyebrow="FIELD PULSE" title="Nearby communities" action={<button className="icon-button" onClick={() => navigate('Needs registry')} title="Open needs"><ArrowRight size={16} /></button>} /><div className="map-preview"><div className="mountain mountain-back" /><div className="mountain mountain-front" /><span className="campus-pin"><MapPin size={13} />Campus</span><i className="map-point point-a" /><i className="map-point point-b" /><i className="map-point point-c" /><span className="map-label map-label-a">Chail · 4 needs</span><span className="map-label map-label-b">Kandaghat · 7 needs</span></div><div className="map-caption"><span><i className="gold-dot" />Active need</span><small>Not a live map</small></div></Panel></div>
    <div className="columns lower"><Panel><PanelTitle eyebrow="MATCH DESK" title="Recommendations to review" action={<button className="text-button" onClick={() => navigate('Match review')}>Open desk <ArrowRight size={14} /></button>} />{matches.filter((match) => match.status === 'Suggested').slice(0, 3).map((match) => <button className="match-row" key={match.id} onClick={() => navigate('Match review')}><span className="category-icon">{match.category[0]}</span><span className="match-copy"><b>{match.item}</b><small>{match.village} · {match.reason}</small></span><span className="fit-pill">{match.score}% fit</span></button>)}</Panel><Panel><PanelTitle eyebrow="RECENT DONATIONS" title="Last added" action={<button className="text-button" onClick={() => navigate('Donate an item')}>Add item <Plus size={14} /></button>} />{items.slice(0, 3).map((item) => <div className="recent-row" key={item.id}><Package size={16} /><span><b>{item.title}</b><small>{item.category} · {item.quantity} units</small></span><Status value={item.status} /></div>)}</Panel></div>
    <p className="privacy-note"><ShieldCheck size={14} />Donor contact details are private and never shown on public item cards.</p>
  </>
}

function Donate({ onSave }: { onSave: (item: Item) => void }) {
  const [error, setError] = useState('')
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = new FormData(event.currentTarget); const title = String(data.get('title')).trim(); const quantity = Number(data.get('quantity')); if (!title || quantity < 1) { setError('Add a title and positive quantity.'); return } onSave({ id: `GB-${Date.now().toString().slice(-4)}`, title, category: String(data.get('category')), quantity, age: String(data.get('age')), condition: Number(data.get('condition')), status: 'In review' }); event.currentTarget.reset(); setError('') }
  return <><Heading eyebrow="DONOR WORKSPACE" title="Offer something useful" description="Add a clear listing for the college committee to review." /><div className="form-layout"><form className="panel form-panel" onSubmit={submit}><PanelTitle eyebrow="NEW DONATION" title="Item details" /><label className="field">Item title<input name="title" placeholder="e.g. Warm woollen blanket" maxLength={120} required /></label><div className="form-two"><label className="field">Category<select name="category">{['Clothes', 'Books', 'Stationery', 'Toys', 'Utensils', 'Blankets', 'Electronics', 'Other'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="field">Quantity<input type="number" name="quantity" min="1" max="10000" defaultValue="1" required /></label></div><div className="form-two"><label className="field">Age group<select name="age">{['Infant', 'Children', 'Teens', 'Adults', 'All ages'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="field">Condition · 1 to 10<input type="number" name="condition" min="1" max="10" defaultValue="8" required /></label></div><label className="field">Description<textarea name="description" rows={4} maxLength={700} placeholder="Size, material, missing parts, or anything a coordinator should know." /></label><label className="field">Photos · optional, up to 4<input type="file" name="photos" accept="image/jpeg,image/png,image/webp" multiple /></label>{error && <p className="error-text" role="alert">{error}</p>}<label className="check-line"><input type="checkbox" required />I confirm this item is clean, safe, and suitable to donate.</label><button className="primary-button" type="submit"><Package size={16} />Submit for review</button></form><aside className="form-aside"><ShieldCheck size={20} /><h3>Good donations go further</h3><p>Items are reviewed before they are visible to coordinators. Please do not donate food, medicine, damaged goods, or unsafe electronics.</p><small>Image validation and model suggestions are not connected in this demo.</small></aside></div></>
}

function Needs({ needs, onSave }: { needs: Need[]; onSave: (need: Need) => void }) {
  const [error, setError] = useState('')
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = new FormData(event.currentTarget); const village = String(data.get('village')).trim(); const quantity = Number(data.get('quantity')); if (!village || quantity < 1) { setError('Village and positive quantity are required.'); return } onSave({ id: `NE-${Date.now().toString().slice(-3)}`, village, category: String(data.get('category')), quantity, urgency: Number(data.get('urgency')), age: String(data.get('age')), deadline: String(data.get('deadline') || 'To be confirmed'), status: 'Open' }); event.currentTarget.reset(); setError('') }
  return <><Heading eyebrow="COORDINATOR WORKSPACE" title="Needs registry" description="Record a community request and confirm details with the village." /><div className="needs-layout"><form className="panel need-form" onSubmit={submit}><PanelTitle eyebrow="NEW REQUEST" title="What is needed?" /><label className="field">Village / institution<input name="village" placeholder="Village, school, anganwadi or NGO" required /></label><div className="form-two"><label className="field">Category<select name="category">{['Clothes', 'Books', 'Stationery', 'Toys', 'Utensils', 'Blankets', 'Electronics', 'Other'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="field">Quantity<input type="number" name="quantity" min="1" defaultValue="10" /></label></div><div className="form-two"><label className="field">Age group<select name="age">{['Infant', 'Children', 'Teens', 'Adults', 'All ages'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="field">Urgency<select name="urgency" defaultValue="3"><option value="1">1 · Low</option><option value="2">2</option><option value="3">3 · Medium</option><option value="4">4</option><option value="5">5 · Urgent</option></select></label></div><label className="field">Deadline<input type="date" name="deadline" /></label><label className="field">Notes / voice transcription<textarea rows={4} placeholder="Hindi or English notes. Voice input can be connected later." /></label>{error && <p className="error-text" role="alert">{error}</p>}<button className="primary-button" type="submit"><Plus size={16} />Post need</button></form><Panel><PanelTitle eyebrow="ACTIVE REGISTRY" title="Open requests" action={<span className="count-pill">{needs.length} requests</span>} />{needs.map((need) => <div className="need-row" key={need.id}><span className={`urgency u${need.urgency}`}>U{need.urgency}</span><span className="need-copy"><b>{need.category} · {need.quantity} units</b><small>{need.village} · {need.age} · Due {need.deadline}</small></span><Status value={need.status} /></div>)}</Panel></div></>
}

function MatchDesk({ matches, onUpdate }: { matches: Match[]; onUpdate: (id: string, status: string, rejection?: string) => void }) {
  const [reasons, setReasons] = useState<Record<string, string>>({})
  return <><Heading eyebrow="COORDINATOR WORKSPACE" title="Match review" description="Review suggestions, then accept or reject with a reason." action={<span className="sample-tag"><Sparkles size={14} />Rules baseline · v1</span>} /><div className="match-toolbar"><b>{matches.filter((match) => match.status === 'Suggested').length} suggestions</b><span>Ranked by fit · demo records</span></div>{matches.map((match) => <Panel className="review-card" key={match.id}><div className="review-head"><span className="category-icon large">{match.category[0]}</span><div className="review-detail"><small>{match.id} · {match.category}</small><h2>{match.item}</h2><p><MapPin size={13} />{match.village}</p><span className="reason"><Sparkles size={13} />{match.reason}</span></div><strong className="score">{match.score}%<small>fit</small></strong><Status value={match.status} /></div>{match.status === 'Suggested' && <div className="review-actions"><select aria-label={`Rejection reason for ${match.id}`} value={reasons[match.id] ?? ''} onChange={(event) => setReasons((current) => ({ ...current, [match.id]: event.target.value }))}><option value="">Reason if rejecting…</option>{['Condition does not fit', 'Quantity is different', 'Age group mismatch', 'Need already met', 'Transport constraint'].map((reason) => <option key={reason}>{reason}</option>)}</select><button className="outline-button" disabled={!reasons[match.id]} onClick={() => onUpdate(match.id, 'Rejected', reasons[match.id])}><X size={14} />Reject</button><button className="primary-button" onClick={() => onUpdate(match.id, 'Accepted')}><Check size={14} />Accept match</button></div>}{match.status === 'Rejected' && <p className="rejection-note">Rejection recorded: {match.rejection}</p>}{match.status === 'Accepted' && <p className="accepted-note"><CheckCircle2 size={14} />Accepted · ready to schedule pickup</p>}</Panel>)}</>
}

function Tasks({ tasks, setTasks, setToast }: { tasks: Task[]; setTasks: (updater: (current: Task[]) => Task[]) => void; setToast: (message: string) => void }) {
  return <><Heading eyebrow="VOLUNTEER WORKSPACE" title="Pickup tasks" description="Claim a route, coordinate the handoff, and confirm the delivery." /><Panel className="route-banner"><Truck size={18} /><span><b>Campus pickup point</b><small>College north gate · exact donor locations shared only after assignment</small></span><span className="count-pill">{tasks.filter((task) => task.status === 'Available').length} routes available</span></Panel>{tasks.map((task) => <Panel className="task-card" key={task.id}><span className="category-icon"><Truck size={17} /></span><span className="task-copy"><small>{task.id} · {task.items} donations</small><b>{task.village}</b><span><MapPin size={13} />{task.route}</span><small><Clock3 size={12} />{task.date}</small></span><Status value={task.status} /><button className="primary-button" onClick={() => { const next = task.status === 'Available' ? 'Claimed' : 'Delivered'; setTasks((current) => current.map((value) => value.id === task.id ? { ...value, status: next } : value)); setToast(`Route ${next.toLowerCase()} in demo.`) }}>{task.status === 'Available' ? 'Claim route' : 'Mark delivered'} <ArrowRight size={14} /></button></Panel>)}<p className="privacy-note"><ShieldCheck size={14} />Donor addresses stay hidden until a volunteer is assigned to a pickup.</p></>
}

function Analytics({ items, needs, matches }: { items: Item[]; needs: Need[]; matches: Match[] }) {
  return <><Heading eyebrow="COLLEGE COMMITTEE" title="Impact & analytics" description="A transparent view of supply, requests, and delivery progress." action={<button className="outline-button"><FileImage size={14} />Export report</button>} /><div className="demo-notice"><Sparkles size={15} />Illustrative dashboard values are sample data until the API is connected. This is not pilot impact.</div><div className="stats"><Stat label="Items listed" value={`${items.length + 124}`} note="All categories · sample" icon={Package} /><Stat label="Needs served" value="62" note="Recipient-confirmed · sample" icon={CheckCircle2} /><Stat label="Fulfillment rate" value="71%" note="Confirmed / accepted · sample" icon={Activity} /><Stat label="Median time to match" value="4.2d" note="Suggestion to acceptance · sample" icon={Clock3} /></div><div className="columns"><Panel><PanelTitle eyebrow="CATEGORY BREAKDOWN" title="Donations and requests" /><div className="analytics-bars">{[['Blankets', 74, 88], ['Books', 61, 58], ['Clothes', 48, 69], ['Stationery', 83, 44]].map(([name, supply, demand]) => <div className="analytics-row" key={String(name)}><span>{name}</span><div><i style={{ width: `${supply}%` }} /><b style={{ width: `${demand}%` }} /></div></div>)}</div><div className="legend"><span><i className="green-dot" />Listed units</span><span><i className="gold-dot" />Requested units</span></div></Panel><Panel><PanelTitle eyebrow="MATCH FUNNEL" title="Where items move" />{[['Uploaded', 100, '286'], ['Suggested', 82, '235'], ['Accepted', 61, '175'], ['Delivered', 49, '140'], ['Confirmed', 41, '118']].map(([label, width, count]) => <div className="funnel-row" key={String(label)}><span>{label}</span><div><i style={{ width: `${width}%` }} /></div><b>{count}</b></div>)}</Panel></div><Panel className="insight-panel"><Sparkles size={17} /><div><p className="eyebrow">COMPUTED SUMMARY · SAMPLE</p><h2>Winter goods are outpacing approved supply.</h2><p>Use a nearby pickup route for blanket requests before the cold-weather drive. Summary numbers are illustrative until the analytics API is connected.</p></div></Panel><p className="privacy-note"><Leaf size={14} />Impact totals should count only recipient-confirmed real deliveries, never synthetic or merely accepted matches.</p><span className="sr-only">{needs.length} needs and {matches.length} matches in current browser state.</span></>
}

function Admin({ items, setItems, setToast }: { items: Item[]; setItems: (updater: (current: Item[]) => Item[]) => void; setToast: (message: string) => void }) {
  const pending = items.filter((item) => item.status === 'In review')
  return <><Heading eyebrow="COLLEGE COMMITTEE" title="Admin desk" description="Moderate listings before they reach coordinators." action={<button className="outline-button"><ShieldCheck size={14} />Audit log</button>} /><div className="admin-metrics"><Panel><Users size={17} /><b>4</b><small>Accounts awaiting verification · sample</small></Panel><Panel><FileImage size={17} /><b>{pending.length + 3}</b><small>Listings awaiting moderation</small></Panel></div><Panel><PanelTitle eyebrow="LISTING MODERATION" title="Items to review" action={<span className="count-pill">{pending.length} in queue</span>} />{pending.length ? pending.map((item) => <div className="admin-item" key={item.id}><span className="category-icon"><Package size={16} /></span><span><b>{item.title}</b><small>{item.category} · {item.quantity} units · condition {item.condition}/10</small></span><button className="outline-button" onClick={() => { setItems((current) => current.map((value) => value.id === item.id ? { ...value, status: 'Rejected' } : value)); setToast('Listing rejected in demo.') }}><X size={14} />Reject</button><button className="primary-button" onClick={() => { setItems((current) => current.map((value) => value.id === item.id ? { ...value, status: 'Approved' } : value)); setToast('Listing approved in demo.') }}><Check size={14} />Approve</button></div>) : <div className="empty-state"><CheckCircle2 size={22} /><b>Nothing waiting for review</b><span>New submissions will appear here.</span></div>}</Panel><p className="privacy-note"><ShieldCheck size={14} />Production verification needs college identity, recipient evidence, audit events, and server-side authorization. This demo does not grant or verify accounts.</p></>
}

export default App
