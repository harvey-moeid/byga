import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  // base './' (relatif) -- GitHub Pages project site disajikan di
  // /<nama-repo>/, bukan di root domain. Dengan path relatif, hasil build
  // jalan di mana pun tanpa perlu meng-hardcode nama repo.
  base: './',

  // Tailwind v4 lewat plugin Vite: CSS di-generate saat build (hanya class yang
  // dipakai), menggantikan <script src="cdn.tailwindcss.com"> versi lama yang
  // memang tidak ditujukan untuk production.
  plugins: [react(), tailwindcss()],
});
