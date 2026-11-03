import { randomBytes, timingSafeEqual } from 'node:crypto'
import { createServer } from 'node:http'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

/** Pi and its shell tools receive a revocable local route, never the saved key.
 * Each Pi process keeps its own route through completion, even during rotation. */
export async function openModelRelay(secret: string) {
  const upstream =
    (process.env.ADMIN_DEEPSEEK_UPSTREAM || 'https://api.deepseek.com').replace(/\/+$/, '') + '/chat/completions'
  const ticket = randomBytes(32).toString('hex')
  const expected = Buffer.from('/' + ticket + '/chat/completions')
  const server = createServer(async (req, res) => {
    const actual = Buffer.from(req.url || '')
    if (req.method !== 'POST' || actual.length !== expected.length || !timingSafeEqual(actual, expected)) {
      res.writeHead(404).end()
      return
    }
    const controller = new AbortController()
    res.on('close', () => controller.abort())
    try {
      const response = await fetch(upstream, {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + secret, 'Content-Type': 'application/json' },
        body: req,
        duplex: 'half',
        redirect: 'error',
        signal: controller.signal,
      } as RequestInit)
      // An upstream error page may echo request headers. Only return the status.
      if (!response.ok || !response.body) {
        await response.body?.cancel()
        res.writeHead(response.status).end('Model provider rejected the request')
        return
      }
      res.writeHead(response.status, {
        'Content-Type': response.headers.get('content-type') || 'application/json',
      })
      await pipeline(Readable.fromWeb(response.body), res)
    } catch {
      if (!res.headersSent) res.writeHead(502)
      res.end()
    }
  })
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const port = (server.address() as { port: number }).port
  server.unref()
  return {
    url: `http://127.0.0.1:${port}/${ticket}`,
    close() {
      server.close()
      server.closeAllConnections()
    },
  }
}
