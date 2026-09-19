import type { ConnectionStatus } from '../hooks/useStateJson';

const DOT: Record<ConnectionStatus['kind'], string> = {
  loading: 'bg-slate-600',
  ok: 'bg-emerald-500',
  error: 'bg-red-500',
};

function label(status: ConnectionStatus): string {
  switch (status.kind) {
    case 'loading':
      return 'memuat...';
    case 'ok':
      return 'terhubung';
    case 'error':
      return `gagal memuat: ${status.message}`;
  }
}

export default function StatusIndicator({ status }: { status: ConnectionStatus }) {
  return (
    // role="status" -> screen reader membacakan perubahan koneksi secara otomatis.
    <div className="flex items-center gap-2" role="status">
      <span className={`w-2.5 h-2.5 rounded-full ${DOT[status.kind]}`} aria-hidden="true" />
      <span className="text-sm text-slate-400">{label(status)}</span>
    </div>
  );
}
