import { useMemo, useState } from 'react';
import { fmt, fmtTime } from '../lib/format';
import type { Candle } from '../types';

interface FullChartProps {
  candles: Candle[];
  price: number | null | undefined;
  lastRunAt?: string | null;
}

const W = 720;
const H = 340;
const AXIS_W = 66;
const PAD_TOP = 18;
const PAD_BOTTOM = 26;
const GRID_LINES = 5;
const WINDOWS = [24, 48, 72, 96];

function clamp(n: number, min: number, max: number) { return Math.max(min, Math.min(max, n)); }

export default function FullChart({ candles, price, lastRunAt }: FullChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [windowSize, setWindowSize] = useState(48);
  const [showGrid, setShowGrid] = useState(true);
  const [showPriceLine, setShowPriceLine] = useState(true);
  const [autoFit, setAutoFit] = useState(true);

  const shown = useMemo(() => candles.slice(-Math.min(windowSize, candles.length)), [candles, windowSize]);
  const chartW = W - AXIS_W;
  const plotH = H - PAD_TOP - PAD_BOTTOM;
  const highs = shown.map(c => c.h);
  const lows = shown.map(c => c.l);
  const rawMax = shown.length ? Math.max(...highs) : 0;
  const rawMin = shown.length ? Math.min(...lows) : 0;
  const rawRange = rawMax - rawMin || rawMax || 1;
  const extra = autoFit ? rawRange * 0.06 : 0;
  const max = rawMax + extra;
  const min = Math.max(0, rawMin - extra);
  const range = max - min || 1;
  const slot = shown.length ? chartW / shown.length : chartW;
  const bodyW = clamp(slot * 0.62, 2, 11);
  const y = (p: number) => PAD_TOP + (1 - (p - min) / range) * plotH;
  const hovered = hoverIdx != null ? shown[hoverIdx] : null;
  const last = shown.at(-1);
  const change = last && last.o ? ((last.c - last.o) / last.o) * 100 : null;
  const gridPrices = Array.from({ length: GRID_LINES + 1 }, (_, i) => min + (range * i) / GRID_LINES);

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!shown.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xPx = ((e.clientX - rect.left) / rect.width) * W - AXIS_W;
    setHoverIdx(clamp(Math.floor(xPx / slot), 0, shown.length - 1));
  };

  return <section className="chart-terminal chart-wrap full-chart">
    <div className="chart-terminal-head">
      <div>
        <div className="chart-symbol"><span className="live-dot" />BTC/USDT <span className="chart-timeframe">15m</span></div>
        <div className="chart-price-line"><strong>{price == null ? '-' : fmt(price)}</strong>{change != null && <span className={change >= 0 ? 'positive' : 'negative'}>{change >= 0 ? '+' : ''}{change.toFixed(2)}%</span>}</div>
        <span className="muted">Update {fmtTime(lastRunAt)} · {shown.length} candle ditampilkan</span>
      </div>
      <div className="chart-range-group" role="group" aria-label="Rentang candle">
        {WINDOWS.map(w => <button key={w} className={windowSize === w ? 'active' : ''} onClick={() => setWindowSize(w)}>{w === 96 ? '1D' : `${w / 4}H`}</button>)}
      </div>
    </div>

    <div className="chart-toolbar">
      <span className="toolbar-label">BTCUSDT · Binance</span>
      <div className="chart-tools">
        <button className={showGrid ? 'tool-active' : ''} onClick={() => setShowGrid(v => !v)}>Grid</button>
        <button className={showPriceLine ? 'tool-active' : ''} onClick={() => setShowPriceLine(v => !v)}>Price</button>
        <button className={autoFit ? 'tool-active' : ''} onClick={() => setAutoFit(v => !v)}>Auto fit</button>
      </div>
    </div>

    {shown.length ? <>
      <div className="chart-canvas-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} className="chart candles full terminal-svg" role="img" aria-label="Grafik candlestick BTC/USDT 15 menit" onMouseMove={handleMove} onMouseLeave={() => setHoverIdx(null)}>
          {showGrid && gridPrices.map((p, i) => <g key={`grid-${i}`}>
            <line x1={AXIS_W} x2={W} y1={y(p)} y2={y(p)} stroke="#173b60" strokeWidth={1} />
            <text x={AXIS_W - 8} y={y(p) + 3} textAnchor="end" fontSize="9" fill="#7891b1">{fmt(p)}</text>
          </g>)}
          {shown.map((c, i) => {
            const cx = AXIS_W + i * slot + slot / 2;
            const up = c.c >= c.o;
            const color = up ? '#00e5a0' : '#ef476f';
            const bodyTop = Math.min(y(c.o), y(c.c));
            const bodyHeight = Math.max(1.5, Math.abs(y(c.c) - y(c.o)));
            const dim = hoverIdx != null && hoverIdx !== i;
            return <g key={c.t} opacity={dim ? .34 : 1}>
              <line x1={cx} x2={cx} y1={y(c.h)} y2={y(c.l)} stroke={color} strokeWidth={1.15} />
              <rect x={cx - bodyW / 2} y={bodyTop} width={bodyW} height={bodyHeight} rx=".8" fill={color} />
            </g>;
          })}
          {showPriceLine && price != null && price >= min && price <= max && <g>
            <line x1={AXIS_W} x2={W} y1={y(price)} y2={y(price)} stroke="#7b8fae" strokeWidth="1" strokeDasharray="4 4" />
            <rect x={W - AXIS_W + 4} y={y(price) - 9} width={AXIS_W - 8} height={18} rx="4" fill="#173b60" />
            <text x={W - 8} y={y(price) + 3} textAnchor="end" fontSize="9" fill="#e8f1ff">{fmt(price)}</text>
          </g>}
          {hoverIdx != null && <g>
            <line x1={AXIS_W + hoverIdx * slot + slot / 2} x2={AXIS_W + hoverIdx * slot + slot / 2} y1={PAD_TOP} y2={H - PAD_BOTTOM} stroke="#557396" strokeWidth="1" strokeDasharray="3 3" />
            <line x1={AXIS_W} x2={W} y1={y(hovered?.c ?? 0)} y2={y(hovered?.c ?? 0)} stroke="#557396" strokeWidth="1" strokeDasharray="3 3" />
          </g>}
          {shown.map((c, i) => i % Math.max(1, Math.floor(shown.length / 6)) === 0 && <text key={`time-${c.t}`} x={AXIS_W + i * slot + slot / 2} y={H - 7} textAnchor="middle" fontSize="8" fill="#607b9d">{new Date(c.t).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</text>)}
        </svg>
      </div>

      <div className="chart-legend-row">
        <span><i className="dot up" />Bullish</span><span><i className="dot down" />Bearish</span><span className="legend-live"><i className="dot live" />Live price</span>
      </div>

      {hovered ? <div className="ohlc-panel">
        <div><small>Waktu</small><b>{fmtTime(new Date(hovered.t).toISOString())}</b></div>
        <div><small>Open</small><b>{fmt(hovered.o)}</b></div>
        <div><small>High</small><b className="positive">{fmt(hovered.h)}</b></div>
        <div><small>Low</small><b className="negative">{fmt(hovered.l)}</b></div>
        <div><small>Close</small><b>{fmt(hovered.c)}</b></div>
      </div> : <div className="chart-summary-grid">
        <div><small>High</small><b className="positive">{fmt(rawMax)}</b></div>
        <div><small>Low</small><b className="negative">{fmt(rawMin)}</b></div>
        <div><small>Range</small><b>{fmt(rawRange)}</b></div>
        <div><small>Last candle</small><b>{last ? fmt(last.c) : '-'}</b></div>
      </div>}

      <div className="chart-terminal-footer">
        <span>Data source <b>state.json</b></span>
        <span>Engine <b>BYGA</b></span>
        <span>Interval <b>15m</b></span>
      </div>
    </> : <div className="empty">Data candle belum tersedia, menunggu run bot berikutnya.</div>}
  </section>;
}
