/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TOKEN_URL?: string;
  readonly VITE_ROOM_PREFIX?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
