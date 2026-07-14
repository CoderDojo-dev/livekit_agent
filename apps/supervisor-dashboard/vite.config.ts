import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5174,
  },

  optimizeDeps: {
    include: [
      "flatpickr",
      "@carbon/react",
    ],
  },

  build: {
    commonjsOptions: {
      include: [
        /node_modules/,
      ],
    },
  },
});