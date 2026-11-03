/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

declare module 'virtual:skill-docs' {
  interface DocPage { key: string; title: string; html: string }
  const skills: { id: string; summary: string; pages: DocPage[] }[]
  export default skills
}
