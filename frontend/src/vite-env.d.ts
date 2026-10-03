/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/react" />

declare const __APP_BUILD_TIME__: string

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_WEBAUTHN_RP_ID: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
