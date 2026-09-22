import type { ReactNode, SVGProps } from 'react';

type IconName = 'menu' | 'home' | 'chart' | 'signals' | 'history' | 'settings' | 'filter' | 'database' | 'clock' | 'plug' | 'target' | 'trend' | 'close' | 'chevron-right' | 'chevron-left';

const paths: Record<IconName, ReactNode> = {
  menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  home: <><path d="m3 10 9-7 9 7" /><path d="M5 9.5V21h14V9.5" /><path d="M9 21v-6h6v6" /></>,
  chart: <><path d="M4 19V5M4 19h16" /><path d="m7 15 4-5 3 3 5-7" /></>,
  signals: <><path d="M4 19V5M4 19h16" /><path d="M7 15v-3M11 15V8M15 15v-5M19 15v-8" /></>,
  history: <><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v5h4M9 12h6M9 16h6" /></>,
  settings: <><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" /><path d="m19.4 15 .1.1a2 2 0 0 1-2.8 2.8l-.1-.1a2 2 0 0 0-3.4 1.4v.2a2 2 0 0 1-4 0v-.2A2 2 0 0 0 5.8 17.8l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A2 2 0 0 0 1.6 11.6v-.2a2 2 0 0 1 4 0v.2a2 2 0 0 0 3.4-1.4V10a2 2 0 0 1 4 0v.2a2 2 0 0 0 3.4 1.4l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a2 2 0 0 0 .2 3.4Z" /></>,
  filter: <><path d="M4 5h16l-6.5 7v5l-5 2v-7z" /></>,
  database: <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
  plug: <><path d="M8 3v6M16 3v6M6 9h12v2a6 6 0 0 1-12 0zM12 17v4" /></>,
  target: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="1" /></>,
  trend: <><path d="M4 17 10 11l4 4 6-8" /><path d="M15 7h5v5" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  'chevron-right': <path d="m9 5 7 7-7 7" />,
  'chevron-left': <path d="m15 5-7 7 7 7" />,
};

export default function Icon({ name, size = 18, strokeWidth = 1.8, className = '', ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: number; strokeWidth?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className} {...props}>{paths[name]}</svg>;
}

export function BrandMark({ size = 34 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <defs><linearGradient id="byga-mark" x1="5" y1="4" x2="35" y2="36" gradientUnits="userSpaceOnUse"><stop stopColor="#5CFFE0"/><stop offset="1" stopColor="#00B982"/></linearGradient></defs>
    <circle cx="20" cy="20" r="17" stroke="url(#byga-mark)" strokeWidth="1.5" opacity=".35" />
    <path d="M12 27V13h9.2c3.2 0 5.2 1.4 5.2 3.7 0 1.4-.8 2.5-2.1 3.1 1.8.5 2.8 1.7 2.8 3.5 0 2.6-2.2 4.2-5.7 4.2H12Z" fill="url(#byga-mark)" />
    <path d="M16 16.5h4.7c1.1 0 1.7.4 1.7 1.2 0 .8-.6 1.2-1.7 1.2H16v-2.4Zm0 5.1h5.1c1.2 0 1.9.4 1.9 1.3s-.7 1.3-1.9 1.3H16v-2.6Z" fill="#041326" />
  </svg>;
}
