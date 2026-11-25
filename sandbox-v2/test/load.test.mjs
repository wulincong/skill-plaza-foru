import assert from 'node:assert/strict'
import { readdirSync } from 'node:fs'
import { test } from 'node:test'

/* node --check 对 .ts 文件不可靠，这里真正加载每个模块，保证它们能被 Node 直接运行。
   可执行脚本必须自带“只有被直接调用才执行”的入口保护，所以这里加载它们不应产生任何副作用。 */
for (const directory of ['../src', '../bin', '../image']) {
  test(`加载 ${directory} 下的全部模块`, async () => {
    const entries = readdirSync(new URL(`${directory}/`, import.meta.url))
    const files = entries.filter((name) => /\.(ts|mjs)$/.test(name) && !name.includes('.test.'))
    assert.ok(files.length > 0)
    for (const name of files) await import(new URL(`${directory}/${name}`, import.meta.url))
  })
}
