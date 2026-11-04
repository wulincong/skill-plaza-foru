import type { Plugin } from 'vite'
import { watch, watchFile, unwatchFile, type FSWatcher, type Stats } from 'node:fs'
import { resolve } from 'node:path'
import { collectDocs, guideFile, hasSkillDocs, publicCatalog, publicGuide, publicIds, repoRoot, skillRoot } from './skill-docs.mjs'

const moduleId = 'virtual:skill-docs'
const availabilityId = 'virtual:skill-doc-availability'

function watchDocsDir(dir: string, reload: () => void) {
  let files: FSWatcher | undefined
  function attach() {
    files?.close()
    try {
      files = watch(dir, (event, name) => {
        if (event === 'change' && (!name || name.endsWith('.md'))) reload()
      })
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code
      if (code !== 'ENOENT' && code !== 'ENOTDIR') throw error
    }
  }
  // Directory changes cover added or removed pages, including a whole skill appearing after startup.
  const onDirectory = (current: Stats, previous: Stats) => {
    if (!current.isDirectory() && !previous.isDirectory()) return
    attach()
    reload()
  }
  watchFile(dir, { interval: 500, persistent: false }, onDirectory)
  attach()
  return () => {
    unwatchFile(dir, onDirectory)
    files?.close()
  }
}

export function skillDocsPlugin(): Plugin {
  const stopWatching: (() => void)[] = []
  return {
    name: 'plaza-skill-docs',
    resolveId(id) {
      if (id === moduleId || id === availabilityId) return '\0' + id
    },
    load(id) {
      if (id === '\0' + moduleId) {
        return `export const guide = ${JSON.stringify(publicGuide())};\nexport default ${JSON.stringify(publicCatalog(collectDocs()))}`
      }
      if (id === '\0' + availabilityId) {
        const availability = Object.fromEntries(publicIds.map(id => [id, hasSkillDocs(repoRoot, id)]))
        return `export default ${JSON.stringify(availability)}`
      }
    },
    configureServer(server) {
      const guidePath = resolve(repoRoot, guideFile)
      function reload(ids: string[]) {
        const loaded = ids.map(id => server.moduleGraph.getModuleById('\0' + id)).filter(mod => mod !== undefined)
        for (const mod of loaded) server.moduleGraph.invalidateModule(mod)
        if (loaded.length) server.ws.send({ type: 'full-reload' })
      }
      server.watcher.add(guidePath)
      for (const id of publicIds) {
        const dir = resolve(repoRoot, skillRoot, id, 'docs')
        stopWatching.push(watchDocsDir(dir, () => reload([moduleId, availabilityId])))
      }
      server.watcher.on('all', (event, file) => {
        if (resolve(file) === guidePath && ['change', 'add', 'unlink'].includes(event)) reload([moduleId])
      })
    },
    closeBundle() {
      for (const stop of stopWatching.splice(0)) stop()
    },
  }
}
