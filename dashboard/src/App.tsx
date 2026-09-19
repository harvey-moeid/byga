import { useMemo, useState } from 'react';
import { REFRESH_MS, STATE_URL } from './config';
import { useStateJson } from './hooks/useStateJson';
import { fmt, fmtTime } from './lib/format';
import { computeStats } from './lib/stats';
import type { Signal } from './types';
import StatusIndicator from './components/StatusIndicator';

const navItems = [
  { id: 'home', label: 'Beranda', icon: '⌂' },
  { id: 'signals', label: 'Sinyal', icon: 'ϟ' },
  { id: 'history', label: 'Riwayat', icon: '◷' },
  { id: 'settings', label: 'Pengaturan', icon: '⚙' },
] as const;
type Page = typeof navItems[number]['id'];
const PAGE_SIZE = 6;

function Pager({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return null;
  return <div className="pager">
    <button disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Halaman sebelumnya">‹</button>
    <span>Halaman {page} dari {totalPages}</span>
    <button disabled={page >= totalPages} onClick={() => onChange(page + 1)} aria-label="Halaman berikutnya">›</button>
  </div>;
}

function Logo() { return <span className="brand-mark">△</span>; }
function DirectionBadge({ type }: { type: Signal['type'] }) { return <span className={`direction ${type.toLowerCase()}`}>{type}</span>; }
function StatusPill({ active }: { active: boolean }) { return <span className={`status-pill ${active ? 'active' : 'closed'}`}>{active ? '↔ Masih Aktif' : '✓ Sudah Close'}</span>; }

function SignalCard({ signal, onOpen }: { signal: Signal; onOpen: (s: Signal) => void }) {
  const active = signal.status === 'active';
  return <button className="signal-card" onClick={() => onOpen(signal)}>
    <div className="signal-top"><DirectionBadge type={signal.type} /><div><strong>BTC/USDT</strong><span className="muted">{fmtTime(signal.createdAt)}</span></div><span className="muted">{active ? 'Aktif' : 'Selesai'} ›</span></div>
    <div className="signal-price">{fmt((signal.entryZoneStart + signal.entryZoneEnd) / 2)}</div>
    <div className="signal-levels"><div><small>Entry</small><b>{fmt(signal.entryZoneStart)}</b></div><div><small>TP1</small><b>{fmt(signal.tp1)}</b></div><div><small>SL</small><b>{fmt(signal.stopLoss)}</b></div></div>
    <StatusPill active={active} />
  </button>;
}

function PriceChart({ price, lastRunAt }: { price: number | null | undefined; lastRunAt?: string | null }) {
  // Sparkline di bawah ini ilustratif (dekorasi), bukan data harga asli --
  // kita tidak menyimpan histori harga di state.json. Angka "+1.10%" yang
  // dulu ada di sini dihapus karena hardcode dan tidak dihitung dari data
  // apa pun; diganti dengan waktu run bot terakhir (data asli dari state.json).
  const points = '8,108 30,116 48,90 66,98 86,70 106,80 126,48 146,64 168,36 188,50 208,18 230,30 250,8';
  return <div className="chart-wrap"><div className="chart-head"><div><small>Mark Price (BTC/USDT)</small><h2>{price == null ? '-' : fmt(price)}</h2><span className="muted">Update: {fmtTime(lastRunAt)}</span></div><span className="chart-tag">15m</span></div><svg viewBox="0 0 258 125" className="chart" role="img" aria-label="Grafik harga ilustratif"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#00e5a0" stopOpacity=".3"/><stop offset="100%" stopColor="#00e5a0" stopOpacity="0"/></linearGradient></defs><path d={`M ${points} L250,125 L8,125 Z`} fill="url(#fill)"/><polyline points={points} fill="none" stroke="#00e5a0" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></div>;
}

export default function App() {
  const { data, status } = useStateJson(STATE_URL, REFRESH_MS);
  const stats = useMemo(() => computeStats(data?.signals ?? []), [data]);
  const [page, setPage] = useState<Page>('home');
  const [selected, setSelected] = useState<Signal | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [signalFilter, setSignalFilter] = useState<'all' | 'active' | 'closed'>('all');
  const [signalsPageNum, setSignalsPageNum] = useState(1);
  const [historyPageNum, setHistoryPageNum] = useState(1);

  const openSignal = (signal: Signal) => setSelected(signal);
  const goTo = (p: Page) => { setPage(p); setMenuOpen(false); };
  const setFilter = (f: 'all' | 'active' | 'closed') => { setSignalFilter(f); setSignalsPageNum(1); };
  const allSignals = data?.signals ?? [];
  const filteredSignals = signalFilter === 'all' ? allSignals : allSignals.filter(s => (s.status === 'active') === (signalFilter === 'active'));
  const totalSignalsPages = Math.max(1, Math.ceil(filteredSignals.length / PAGE_SIZE));
  const currentSignalsPage = Math.min(signalsPageNum, totalSignalsPages);
  const pagedSignals = filteredSignals.slice((currentSignalsPage - 1) * PAGE_SIZE, currentSignalsPage * PAGE_SIZE);
  const totalHistoryPages = Math.max(1, Math.ceil(stats.closed.length / PAGE_SIZE));
  const currentHistoryPage = Math.min(historyPageNum, totalHistoryPages);
  const pagedHistory = stats.closed.slice((currentHistoryPage - 1) * PAGE_SIZE, currentHistoryPage * PAGE_SIZE);

  const header = <header className="app-header"><div className="brand"><button className="icon-button" aria-label="Menu" onClick={() => setMenuOpen(true)}>☰</button><Logo /><div><h1>BYGA Signal</h1><p>Trading Bot Dashboard</p></div></div><div className="bot-state"><span /> Bot Aktif</div></header>;

  const menu = menuOpen && <div className="modal-backdrop menu-backdrop" onClick={() => setMenuOpen(false)}><div className="menu-drawer" onClick={e => e.stopPropagation()}><div className="menu-drawer-head"><div className="brand"><Logo /><div><h1>BYGA Signal</h1><p>Trading Bot Dashboard</p></div></div><button className="close-button" onClick={() => setMenuOpen(false)}>×</button></div><nav className="menu-drawer-nav">{navItems.map(item => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => goTo(item.id)}><span>{item.icon}</span>{item.label}</button>)}</nav></div></div>;

  const home = <>
    <PriceChart price={data?.last_price} lastRunAt={data?.last_run_at} />
    <div className="stats-grid"><div className="metric"><span>ϟ</span><small>Sinyal Aktif</small><strong>{stats.active.length}</strong><em>{stats.activeLong}L / {stats.activeShort}S</em></div><div className="metric"><span>◉</span><small>Win Rate</small><strong>{stats.winRateLabel.split(' ')[0]}</strong><em>{stats.wins}W / {stats.losses}L</em></div><div className="metric"><span>◈</span><small>Cumulative R</small><strong className={stats.cumulativeR >= 0 ? 'positive' : 'negative'}>{stats.cumulativeRLabel}</strong><em>({stats.closed.length} closed)</em></div></div>
    <section className="section"><div className="section-title"><div><h2>Sinyal Terbaru</h2><p>Peluang trading yang sedang dipantau</p></div><button onClick={() => setPage('signals')}>Lihat Semua ›</button></div>{allSignals.slice(0, 3).map(s => <SignalCard key={s.id} signal={s} onOpen={openSignal} />)}{!allSignals.length && <div className="empty">Belum ada data sinyal.</div>}</section>
  </>;

  const signalsPage = <section className="section"><div className="section-title"><div><h2>Daftar Sinyal</h2><p>Semua peluang dari bot</p></div><span className="filter-chip">☷</span></div><div className="tabs"><button className={signalFilter === 'all' ? 'selected' : ''} onClick={() => setFilter('all')}>Semua</button><button className={signalFilter === 'active' ? 'selected' : ''} onClick={() => setFilter('active')}>Aktif</button><button className={signalFilter === 'closed' ? 'selected' : ''} onClick={() => setFilter('closed')}>Close</button></div>{pagedSignals.map(s => <SignalCard key={s.id} signal={s} onOpen={openSignal} />)}{!filteredSignals.length && <div className="empty">Belum ada sinyal.</div>}<Pager page={currentSignalsPage} totalPages={totalSignalsPages} onChange={setSignalsPageNum} /></section>;

  const historyPage = <section className="section"><div className="section-title"><div><h2>Riwayat Trading</h2><p>Ringkasan sinyal yang sudah selesai</p></div></div><div className="history-summary"><div><small>Total Trade</small><b>{stats.closed.length}</b></div><div><small>Win Rate</small><b className="positive">{stats.winRateLabel.split(' ')[0]}</b></div><div><small>Cumulative R</small><b className={stats.cumulativeR >= 0 ? 'positive' : 'negative'}>{stats.cumulativeRLabel}</b></div></div>{pagedHistory.map(s => <SignalCard key={s.id} signal={s} onOpen={openSignal} />)}{!stats.closed.length && <div className="empty">Belum ada riwayat trading.</div>}<Pager page={currentHistoryPage} totalPages={totalHistoryPages} onChange={setHistoryPageNum} /></section>;

  const settingsPage = <section className="section"><div className="section-title"><div><h2>Pengaturan</h2><p>Kelola sumber data dashboard</p></div></div><div className="setting-card"><div className="setting-icon">◉</div><div><small>Sumber Data</small><strong>GitHub (state.json)</strong><p>Update otomatis via GitHub Actions</p></div></div><div className="setting-card"><div className="setting-icon">◷</div><div><small>Interval Update</small><strong>1 menit</strong><p>Data diperbarui otomatis</p></div></div><div className="setting-card"><div className="setting-icon">✓</div><div><small>Status Koneksi</small><strong><StatusIndicator status={status} /></strong><p>GitHub Actions · Cloudflare Pages</p></div></div><div className="info-box"><b>Panduan Penggunaan</b><p>Bot membaca data dari state.json yang diperbarui otomatis oleh GitHub Actions. Gunakan kartu sinyal untuk melihat Entry, TP1, dan Stop Loss.</p></div></section>;

  return <main className="app-shell"><div className="app-container">{header}<div className="page-content">{page === 'home' && home}{page === 'signals' && signalsPage}{page === 'history' && historyPage}{page === 'settings' && settingsPage}</div><nav className="bottom-nav">{navItems.map(item => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => setPage(item.id)}><span>{item.icon}</span>{item.label}</button>)}</nav></div>{menu}{selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><div className="detail-sheet" onClick={e => e.stopPropagation()}><button className="close-button" onClick={() => setSelected(null)}>×</button><div className="detail-title"><Logo /><div><h2>BTC/USDT</h2><p>Detail Sinyal</p></div><DirectionBadge type={selected.type} /></div><PriceChart price={data?.last_price} lastRunAt={data?.last_run_at} /><div className="detail-rows"><div><span>Arah</span><b className="positive">{selected.type}</b></div><div><span>Entry</span><b>{fmt(selected.entryZoneStart)}</b></div><div><span>Take Profit 1 (TP1)</span><b>{fmt(selected.tp1)}</b></div><div><span>Take Profit 2 (TP2)</span><b>{fmt(selected.tp2)}</b></div><div><span>Stop Loss (SL)</span><b>{fmt(selected.stopLoss)}</b></div><div><span>Status</span><StatusPill active={selected.status === 'active'} /></div></div></div></div>}</main>;
}
