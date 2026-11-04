import type { Plugin } from 'vite'
import { dirname, resolve } from 'node:path'
import { collectDocs, guideFile, publicCatalog, publicGuide, publicIds, repoRoot, skillRoot } from './skill-docs.mjs'

const moduleId = 'virtual:skill-docs'

export function skillDocsPlugin(): Plugin {
  return {
    name: 'plaza-skill-docs',
    resolveId(id) {
      if (id === moduleId) return '\0' + id
    },
    load(id) {
      if (id === '\0' + moduleId) {
        return `export const guide = ${JSON.stringify(publicGuide())};\nexport default ${JSON.stringify(publicCatalog(collectDocs()))}`
      }
    },
    configureServer(server) {
      // Vite's watcher has globbing disabled. Directory watches catch new chapters too.
      const dirs = new Set(publicIds.map(id => resolve(repoRoot, skillRoot, id, 'docs')))
      const guidePath = resolve(repoRoot, guideFile)
      server.watcher.add([...dirs, guidePath])
      server.watcher.on('all', (event, file) => {
        if (!['change', 'add', 'unlink'].includes(event)) return
        if (resolve(file) !== guidePath && !(file.endsWith('.md') && dirs.has(dirname(resolve(file))))) return
        const mod = server.moduleGraph.getModuleById('\0' + moduleId)
        if (mod) {
          server.moduleGraph.invalidateModule(mod)
          server.ws.send({ type: 'full-reload' })
        }
      })
    },
  }
}
