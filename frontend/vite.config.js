import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://localhost:8000"; // the FastAPI backend
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": api, "/video": api, "/evidence": api, "/ws": { target: api, ws: true } } },
});
