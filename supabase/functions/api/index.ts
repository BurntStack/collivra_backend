import { Hono, type Context } from 'jsr:@hono/hono@4'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3'
import { normalizeMobile, sendOtp, checkOtp } from './otpService.ts'

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const admin = createClient(SUPABASE_URL, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
  auth: { persistSession: false },
})
const anon = createClient(SUPABASE_URL, Deno.env.get('SUPABASE_ANON_KEY')!, {
  auth: { persistSession: false },
})

const RESEND_SECONDS = 30
const MAX_SENDS_PER_HOUR = 5
// Accounts without an email get a placeholder login address (unique per role).
const PHONE_EMAIL_DOMAIN = Deno.env.get('PHONE_EMAIL_DOMAIN') ?? 'mobile.collivra.app'

const app = new Hono().basePath('/api/v1')

// ---------- helpers ----------
const readJson = (c: Context) => c.req.json().catch(() => ({}))

function validationError(c: Context, err: z.ZodError) {
  const fields: Record<string, string> = {}
  for (const issue of err.issues) fields[issue.path.join('.') || '_'] ??= issue.message
  return c.json({ message: 'Please check the highlighted fields', code: 'validation_error', fields }, 422)
}

const mobileField = z.string().transform((v, ctx) => {
  const m = normalizeMobile(v)
  if (!m) {
    ctx.addIssue({ code: 'custom', message: 'Enter a valid Indian mobile number' })
    return z.NEVER
  }
  return m
})

function nextStep(status: string): 'dashboard' | 'onboarding' | 'pending' {
  if (status === 'active') return 'dashboard'
  if (status === 'unverified' || status === 'needs_info') return 'onboarding'
  return 'pending'
}

// Sends an OTP, enforcing the spec limit of 5 sends per hour per number.
async function sendWithLimit(mobile: string, purpose: string): Promise<'sent' | 'limited'> {
  const since = new Date(Date.now() - 3600_000).toISOString()
  const { count } = await admin.from('otp_send_log')
    .select('*', { count: 'exact', head: true })
    .eq('mobile', mobile).gte('created_at', since)
  if ((count ?? 0) >= MAX_SENDS_PER_HOUR) return 'limited'
  await admin.from('otp_send_log').insert({ mobile, purpose })
  await sendOtp(mobile)
  return 'sent'
}

// Turns a verified user into a normal Supabase session.
async function createSession(userId: string) {
  const { data: u, error: e1 } = await admin.auth.admin.getUserById(userId)
  if (e1 || !u.user?.email) throw new Error('user lookup failed')
  const { data: link, error: e2 } = await admin.auth.admin.generateLink({
    type: 'magiclink', email: u.user.email,
  })
  if (e2) throw e2
  const { data, error: e3 } = await anon.auth.verifyOtp({
    token_hash: link.properties.hashed_token, type: 'magiclink',
  })
  if (e3 || !data.session) throw e3 ?? new Error('no session')
  return data.session
}

// ---------- routes ----------
app.get('/health', (c) => c.json({ ok: true, time: new Date().toISOString() }))


const signupSchema = z.object({
  role: z.enum(['brand', 'creator']),
  name: z.string().trim().min(2, 'Enter your name').max(100),
  mobile: mobileField,
  email: z.preprocess((v) => (v === '' ? undefined : v),
    z.string().trim().email('Enter a valid email').optional()),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  acceptTerms: z.literal(true, { errorMap: () => ({ message: 'Please accept the terms' }) }),
  termsVersion: z.string().min(1, 'Terms version is required'),
})

app.post('/auth/signup', async (c) => {
  const parsed = signupSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { role, name, mobile, email, password, termsVersion } = parsed.data

  const { data: existing } = await admin.from('profiles')
    .select('id').eq('mobile', mobile).eq('role', role).limit(1)
  if (existing?.length) {
    return c.json({ message: 'This mobile number is already registered', code: 'mobile_taken' }, 409)
  }

  const loginEmail = email ?? `${mobile.slice(1)}.${role}@${PHONE_EMAIL_DOMAIN}`
  const { data: created, error } = await admin.auth.admin.createUser({
    email: loginEmail,
    password,
    email_confirm: true,
    user_metadata: { role, name, mobile, terms_version: termsVersion },
  })
  if (error || !created.user) {
    if (error?.code === 'email_exists') {
      return c.json({ message: 'This email is already registered', code: 'email_taken' }, 409)
    }
    throw error ?? new Error('createUser failed')
  }
  const userId = created.user.id

  // The signup trigger stores the login email; clear it if it was only a placeholder.
  if (!email) await admin.from('profiles').update({ email: null }).eq('id', userId)

  try {
    const result = await sendWithLimit(mobile, 'signup')
    if (result === 'limited') {
      return c.json({ message: 'Too many codes requested. Try again later.', code: 'rate_limited' }, 429)
    }
  } catch (e) {
    console.error(e)
    return c.json({ message: 'Account created, but we could not send the code. Please resend it.', code: 'otp_send_failed' }, 502)
  }
  return c.json({ userId, otpSent: true, resendInSeconds: RESEND_SECONDS }, 201)
})

const sendSchema = z.object({ mobile: mobileField, purpose: z.enum(['signup', 'login']) })

app.post('/auth/otp/send', async (c) => {
  const parsed = sendSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { mobile, purpose } = parsed.data

  // Same reply whether or not the number has an account, so numbers can't be probed.
  const { data } = await admin.from('profiles').select('id').eq('mobile', mobile).limit(1)
  if (data?.length) {
    const result = await sendWithLimit(mobile, purpose)
    if (result === 'limited') {
      return c.json({ message: 'Too many codes requested. Try again later.', code: 'rate_limited' }, 429)
    }
  }
  return c.json({ resendInSeconds: RESEND_SECONDS })
})

const verifySchema = z.object({
  mobile: mobileField,
  code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code'),
  purpose: z.enum(['signup', 'login']),
  role: z.enum(['brand', 'creator']).optional(), // only needed if one number has both roles
})

app.post('/auth/otp/verify', async (c) => {
  const parsed = verifySchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { mobile, code, purpose, role } = parsed.data

  const invalid = () =>
    c.json({ message: 'That code is wrong or has expired', code: 'invalid_otp' }, 400)

  if (!(await checkOtp(mobile, code))) return invalid()

  let query = admin.from('profiles')
    .select('id, role, status')
    .eq('mobile', mobile).order('created_at', { ascending: false })
  if (role) query = query.eq('role', role)
  const { data: profiles } = await query
  if (!profiles?.length) return invalid()
  if (purpose === 'login' && profiles.length > 1 && !role) {
    return c.json({ message: 'Choose brand or creator to continue', code: 'role_required' }, 409)
  }

  const profile = profiles[0]
  if (profile.status === 'suspended' || profile.status === 'banned') {
    return c.json({ message: `Your account is ${profile.status}`, code: 'account_blocked' }, 403)
  }

  await admin.from('profiles')
    .update({ mobile_verified_at: new Date().toISOString() })
    .eq('mobile', mobile).is('mobile_verified_at', null)

  const session = await createSession(profile.id)
  return c.json({
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
    expiresIn: session.expires_in,
    role: profile.role,
    status: profile.status,
    next: nextStep(profile.status),
  })
})

// ---------- login, me, refresh ----------
const MAX_FAILED_LOGINS = 5
const LOCK_MINUTES = 15

const loginSchema = z.object({
  identifier: z.string().trim().min(3, 'Enter your mobile number or email'),
  password: z.string().min(1, 'Enter your password'),
  role: z.enum(['brand', 'creator']).optional(), // only needed if one number has both roles
})

async function findProfiles(identifier: string, role?: string) {
  let q = admin.from('profiles')
    .select('id, role, status, mobile_verified_at, failed_logins, locked_until')
  if (identifier.includes('@')) {
    q = q.eq('email', identifier.toLowerCase())
  } else {
    const mobile = normalizeMobile(identifier)
    if (!mobile) return []
    q = q.eq('mobile', mobile)
  }
  if (role) q = q.eq('role', role)
  const { data } = await q
  return data ?? []
}

app.post('/auth/login', async (c) => {
  const parsed = loginSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { identifier, password, role } = parsed.data

  const wrong = () =>
    c.json({ message: 'Wrong mobile/email or password', code: 'invalid_credentials' }, 401)
  const locked = (until: string) =>
    c.json({ message: `Too many wrong attempts. Try again in ${LOCK_MINUTES} minutes.`,
             code: 'account_locked', lockedUntil: until }, 423)

  const profiles = await findProfiles(identifier, role)
  if (!profiles.length) return wrong()
  if (profiles.length > 1) {
    return c.json({ message: 'Choose brand or creator to continue', code: 'role_required' }, 409)
  }
  const p = profiles[0]

  if (p.locked_until && new Date(p.locked_until) > new Date()) return locked(p.locked_until)

  const { data: u } = await admin.auth.admin.getUserById(p.id)
  const { data, error } = await anon.auth.signInWithPassword({
    email: u.user!.email!, password,
  })

  if (error || !data.session) {
    if (error?.status === 429) {
      return c.json({ message: 'Too many attempts. Please wait a moment.', code: 'rate_limited' }, 429)
    }
    const failed = p.failed_logins + 1
    if (failed >= MAX_FAILED_LOGINS) {
      const until = new Date(Date.now() + LOCK_MINUTES * 60_000).toISOString()
      await admin.from('profiles').update({ failed_logins: 0, locked_until: until }).eq('id', p.id)
      return locked(until)
    }
    await admin.from('profiles').update({ failed_logins: failed }).eq('id', p.id)
    return wrong()
  }

  const session = data.session
  if (p.failed_logins || p.locked_until) {
    await admin.from('profiles').update({ failed_logins: 0, locked_until: null }).eq('id', p.id)
  }

  // Status checks happen only after password is verified — prevents account existence probing.
  if (p.status === 'suspended' || p.status === 'banned') {
    await admin.auth.admin.signOut(session.access_token)
    return c.json({ message: `Your account is ${p.status}`, code: 'account_blocked' }, 403)
  }
  if (!p.mobile_verified_at) {
    await admin.auth.admin.signOut(session.access_token)
    return c.json({ message: 'Please verify your mobile number first', code: 'mobile_not_verified' }, 403)
  }

  return c.json({
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
    expiresIn: session.expires_in,
    role: p.role,
    status: p.status,
    next: nextStep(p.status),
  })
})

// Reusable: reads the Bearer token and returns the caller's profile, or null.
async function requireUser(c: Context) {
  const header = c.req.header('Authorization') ?? ''
  const token = header.startsWith('Bearer ') ? header.slice(7).trim() : ''
  if (!token) return null
  // admin.auth.getUser(jwt) validates the token server-side against Supabase Auth.
  const { data, error } = await admin.auth.getUser(token)
  if (error || !data?.user?.id) return null
  const { data: profile } = await admin.from('profiles')
    .select('id, role, status, name, mobile').eq('id', data.user.id).single()
  return profile ?? null
}

app.get('/auth/me', async (c) => {
  const me = await requireUser(c)
  if (!me) return c.json({ message: 'Please sign in again', code: 'unauthorized' }, 401)
  if (me.status === 'suspended' || me.status === 'banned') {
    return c.json({ message: `Your account is ${me.status}`, code: 'account_blocked' }, 403)
  }
  return c.json({ id: me.id, role: me.role, status: me.status, name: me.name, mobile: me.mobile })
})

app.post('/auth/refresh', async (c) => {
  const parsed = z.object({ refreshToken: z.string().min(1) }).safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { data, error } = await anon.auth.refreshSession({ refresh_token: parsed.data.refreshToken })
  if (error || !data.session) {
    return c.json({ message: 'Please sign in again', code: 'unauthorized' }, 401)
  }
  return c.json({
    accessToken: data.session.access_token,
    refreshToken: data.session.refresh_token,
    expiresIn: data.session.expires_in,
  })
})

// Error format from the spec: { message, code?, fields? }
app.notFound((c) => c.json({ message: 'Not found', code: 'not_found' }, 404))
app.onError((err, c) => {
  console.error(err)
  return c.json({ message: 'Something went wrong', code: 'server_error' }, 500)
})

Deno.serve(app.fetch)
