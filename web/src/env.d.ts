/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

declare module 'virtual:skill-docs' {
  type DocBlock = { kind: 'markdown'; html: string } | { kind: 'prompt'; text: string }
  interface DocPage {
    key: string
    title: string
    blocks: DocBlock[]
    outline: { id: string; title: string }[]
  }
  const skills: { id: string; summary: string; pages: DocPage[] }[]
  export default skills
}
