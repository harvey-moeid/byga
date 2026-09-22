import { useState } from 'react';
import { fmt, fmtTime } from '../lib/format';
import type { Candle } from '../types';

interface FullChartProps {
  candles: Candle[];
  price: number | null | undefined;
  lastRunAt?: string | null;
}

const W = 640;
const H = 280;
const AXIS_W = 50;
const PAD_TOP = 14;
const PAD_BOTTOM = 10;
const GRID_LINES = 4;

export default function FullChart({ candles, price, lastRunAt }: FullChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const chartW = W - AXIS_W;
  const plotH = H - PAD_TOP - PAD_BOTTOM;
  const highs = candles.map(c => c.h);
  const lows = candles.map(c => c.l);
  const max = candles.length ? Math.max(...highs) : 0;
  const min = candles.length ? Math.min(...lows) : 0;
  const range = max - min || max || 1;
  const slot = candles.length ? chartW / candles.length : chartW;
  const bodyW = Math.max(2, slot * 0.64);
  const y = (p: number) => PAD_TOP + (1 - (p - min) / range) * plotH;

  const gridPrices = Array.from({ length: GRID_LINES + 1 }, (_, i) => min + (range * i) / GRID_LINES);
  const hovered = hoverIdx != null ? candles[hoverIdx] : null;

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!candles.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xRatio = (e.clientX - rect.left) / rect.width;
    const xPx = xRatio * W - AXIS_W;
    const idx = Math.min(candles.length - 1, Math.max(0, Math.floor(xPx / slot)));
    setHoverIdx(idx);
  };

  return <div className="chart-wrap full-chart">
    <div className="chart-head">
      <div>
        <small>Mark Price (BTC/USDT)</small>
        <h2>{price == null ? '-' : fmt(price)}</h2>
        <span className="muted">Update: {fmtTime(lastRunAt)}</span>
      </div>
      <span className="chart-tag">15m &middot; {candles.length} candle</span>
    </div>
    {candles.length ? <>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart candles full"
        role="img"
        aria-label="Grafik candlestick lengkap BTC/USDT 15 menit"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
        {gridPrices.map((p, i) => <g key={i}>
          <line x1={AXIS_W} x2={W} y1={y(p)} y2={y(p)} stroke="#12375d" strokeWidth={1} />
          <text x={AXIS_W - 6} y={y(p) + 3} textAnchor="end" fontSize="9" fill="#7f94b3">{fmt(p)}</text>
        </g>)}
        {candles.map((c, i) => {
          const cx = AXIS_W + i * slot + slot / 2;
          const up = c.c >= c.o;
          const color = up ? '#00e5a0' : '#ef476f';
          const yOpen = y(c.o), yClose = y(c.c);
          const bodyTop = Math.min(yOpen, yClose);
          const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
          const dim = hoverIdx != null && hoverIdx !== i;
          return <g key={c.t} opacity={dim ? 0.4 : 1}>
            <line x1={cx} x2={cx} y1={y(c.h)} y2={y(c.l)} stroke={color} strokeWidth={1.2} />
            <rect x={cx - bodyW / 2} y={bodyTop} width={bodyW} height={bodyHeight} fill={color} />
          </g>;
        })}
        {hoverIdx != null && <line
          x1={AXIS_W + hoverIdx * slot + slot / 2}
          x2={AXIS_W + hoverIdx * slot + slot / 2}
          y1={PAD_TOP}
          y2={H - PAD_BOTTOM}
          stroke="#4d6a90"
          strokeWidth={1}
          strokeDasharray="3 3"
        />}
      </svg>
      <div className="full-chart-legend">
        <span><i className="dot up" />Naik</span>
        <span><i className="dot down" />Turun</span>
      </div>
      {hovered ? <div className="full-chart-tooltip">
        <div><small>Waktu</small><b>{fmtTime(new Date(hovered.t).toISOString())}</b></div>
        <div><small>Open</small><b>{fmt(hovered.o)}</b></div>
        <div><small>High</small><b className="positive">{fmt(hovered.h)}</b></div>
        <div><small>Low</small><b className="negative">{fmt(hovered.l)}</b></div>
        <div><small>Close</small><b>{fmt(hovered.c)}</b></div>
      </div> : <div className="full-chart-stats">
        <div><small>Tertinggi</small><b className="positive">{fmt(max)}</b></div>
        <div><small>Terendah</small><b className="negative">{fmt(min)}</b></div>
        <div><small>Range</small><b>{fmt(range)}</b></div>
      </div>}
    </> : <div className="empty">Data candle belum tersedia, menunggu run bot berikutnya.</div>}
  </div>;
}
