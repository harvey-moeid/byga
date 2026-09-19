import { useCallback, useState } from 'react';
import { DEFAULT_STATE_URL, STORAGE_KEY } from '../config';

// localStorage bisa melempar error (mode privat, storage diblokir, dll).
// Dashboard harus tetap jalan, jadi semua akses dibungkus try/catch.
function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(value: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* abaikan: URL tetap dipakai untuk sesi ini, hanya tidak tersimpan */
  }
}

/** URL state.json aktif + fungsi untuk menggantinya (dan menyimpannya di browser). */
export function useSourceUrl() {
  const [url, setUrl] = useState<string>(() => readStored() || DEFAULT_STATE_URL);

  const saveUrl = useCallback((next: string) => {
    const trimmed = next.trim();
    if (!trimmed) return;
    writeStored(trimmed);
    setUrl(trimmed);
  }, []);

  return { url, saveUrl };
}
