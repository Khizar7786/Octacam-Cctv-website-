import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { getServerApiOrigin } from "./app/lib/api/server-config.server.ts";

export default defineConfig(({ command }) => ({
  plugins: [tailwindcss(), reactRouter()],
  resolve: {
    alias: {
      "~": fileURLToPath(new URL("./app", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    ...(command === "serve" ? {
      proxy: {
        "/api/v1": {
          target: getServerApiOrigin(),
          changeOrigin: false,
        },
      },
    } : {}),
  },
}));
