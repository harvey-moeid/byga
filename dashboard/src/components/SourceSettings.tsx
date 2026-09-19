import { useState, type FormEvent } from 'react';

interface Props {
  url: string;
  onSave: (url: string) => void;
}

export default function SourceSettings({ url, onSave }: Props) {
  const [draft, setDraft] = useState(url);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSave(draft);
  }

  return (
    <details className="bg-slate-900 rounded-lg p-3 text-sm">
      <summary className="cursor-pointer text-slate-300">Pengaturan sumber data</summary>
      {/* <form> -> tombol Enter di input ikut menyimpan, tanpa handler keyboard manual. */}
      <form onSubmit={handleSubmit} className="mt-3 flex flex-col sm:flex-row gap-2">
        <input
          type="url"
          aria-label="URL state.json"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="https://raw.githubusercontent.com/USER/REPO/main/state.json"
          className="flex-1 bg-slate-800 rounded px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-emerald-500"
        />
        <button
          type="submit"
          className="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded text-sm font-medium"
        >
          Simpan
        </button>
      </form>
      <p className="text-slate-500 mt-2">
        URL disimpan di browser (localStorage). Pastikan repo bersifat public agar raw URL bisa
        diakses tanpa autentikasi.
      </p>
    </details>
  );
}
