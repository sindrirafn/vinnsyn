import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
export default defineConfig({ plugins: [react()], publicDir: fileURLToPath(new URL('./data', import.meta.url)), server: { port: 5174, fs: { strict: true, allow: [fileURLToPath(new URL('.', import.meta.url))] } } });
