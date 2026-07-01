/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_BUSINESS_API_URL?: string;
  readonly VITE_API_ROLE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}