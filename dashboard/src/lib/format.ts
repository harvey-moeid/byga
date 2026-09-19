/** Angka dengan maksimal 2 desimal dan pemisah ribuan; '-' kalau bukan angka. */
export function fmt(n: number | null | undefined): string {
  return typeof n === 'number'
    ? n.toLocaleString('en-US', { maximumFractionDigits: 2 })
    : '-';
}

/** Waktu ISO -> format lokal Indonesia 24 jam; '-' kalau kosong. */
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('id-ID', { hour12: false });
}
