import { Hono } from 'jsr:@hono/hono@4'

const app = new Hono().basePath('/api/v1')

app.get('/health', (c) => c.json({ ok: true, time: new Date().toISOString() }))

// Error format from the spec: { message, code?, fields? }
app.notFound((c) => c.json({ message: 'Not found', code: 'not_found' }, 404))
app.onError((err, c) => {
  console.error(err)
  return c.json({ message: 'Something went wrong', code: 'server_error' }, 500)
})

Deno.serve(app.fetch)
