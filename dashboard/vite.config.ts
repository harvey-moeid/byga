import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  // base './' (relatif) supaya hasil build jalan di mana pun (root domain
  // Cloudflare Pages maupun subpath) tanpa perlu meng-hardcode nama repo.
  base: './',

  // Tailwind v4 lewat plugin Vite: CSS di-generate saat build (hanya class yang
  // dipakai), menggantikan <script src="cdn.tailwindcss.com"> versi lama yang
  // memang tidak ditujukan untuk production.
  plugins: [react(), tailwindcss()],
});
