import { Hono, type Context } from 'jsr:@hono/hono@4'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3'
import { normalizeMobile, sendOtp, checkOtp } from './otpService.ts'
import { encryptField, decryptField, signSocialState, verifySocialState } from './crypto.ts'
import { verifyPan, verifyBank, verifyId } from './kycProvider.ts'

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

const brandSignupSchema = z.object({
  name: z.string().trim().min(2, 'Enter your name').max(100),
  email: z.string().trim().email('Enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  companyName: z.string().trim().min(2, 'Enter your company name').max(100),
})

app.post('/auth/signup', async (c) => {
  const body = await readJson(c)

  // Brand signup flow: { name, email, password, companyName }
  if (body?.companyName || (!body?.mobile && body?.email)) {
    const brandParsed = brandSignupSchema.safeParse(body)
    if (!brandParsed.success) {
      return c.json({
        error: { code: 'validation_error', message: brandParsed.error.errors[0]?.message ?? 'Invalid fields' },
        message: brandParsed.error.errors[0]?.message ?? 'Invalid fields',
        code: 'validation_error',
        fields: Object.fromEntries(brandParsed.error.errors.map((e) => [e.path[0], e.message])),
      }, 422)
    }
    const { name, email, password, companyName } = brandParsed.data

    const { data: existing } = await admin.from('profiles')
      .select('id').eq('email', email.toLowerCase()).limit(1)
    if (existing?.length) {
      return c.json({
        error: { code: 'email_taken', message: 'This email is already registered' },
        message: 'This email is already registered',
        code: 'email_taken',
      }, 409)
    }

    const { data: created, error } = await admin.auth.admin.createUser({
      email: email.toLowerCase(),
      password,
      email_confirm: true,
      user_metadata: { role: 'brand', name, company_name: companyName },
    })
    if (error || !created.user) {
      if (error?.code === 'email_exists') {
        return c.json({
          error: { code: 'email_taken', message: 'This email is already registered' },
          message: 'This email is already registered',
          code: 'email_taken',
        }, 409)
      }
      throw error ?? new Error('createUser failed')
    }

    // Auto sign-in to get session token
    const { data: signin, error: signinErr } = await anon.auth.signInWithPassword({
      email: email.toLowerCase(),
      password,
    })
    if (signinErr || !signin.session) {
      throw signinErr ?? new Error('Auto signin failed')
    }

    // Ensure status is active for the brand
    await admin.from('profiles').update({ status: 'active', company_name: companyName }).eq('id', created.user.id)

    return c.json({
      token: signin.session.access_token,
      user: {
        id: created.user.id,
        name,
        email: email.toLowerCase(),
        companyName,
        role: 'brand',
      },
    }, 201)
  }

  // Mobile / Creator OTP signup flow
  const parsed = signupSchema.safeParse(body)
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
  identifier: z.string().trim().optional(),
  email: z.string().trim().optional(),
  password: z.string().min(1, 'Enter your password'),
  role: z.enum(['brand', 'creator']).optional(), // only needed if one number has both roles
}).refine((d) => d.identifier || d.email, { message: 'Enter your mobile number or email' })

async function findProfiles(identifier: string, role?: string) {
  let q = admin.from('profiles')
    .select('id, role, status, name, company_name, mobile_verified_at, failed_logins, locked_until')
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
  const { password, role } = parsed.data
  const identifier = (parsed.data.identifier || parsed.data.email)!.trim()

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
  // Mobile verification required for mobile accounts; email brand accounts are verified
  if (!p.mobile_verified_at && p.role !== 'brand' && !identifier.includes('@')) {
    await admin.auth.admin.signOut(session.access_token)
    return c.json({ message: 'Please verify your mobile number first', code: 'mobile_not_verified' }, 403)
  }

  return c.json({
    token: session.access_token,
    user: {
      id: p.id,
      name: p.name,
      email: u.user?.email,
      companyName: p.company_name,
      role: p.role,
    },
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
    .select('id, role, status, name, mobile, company_name').eq('id', data.user.id).single()
  if (!profile) return null
  return { ...profile, token, authUser: data.user }
}

async function requireRole(c: Context, role: 'creator' | 'brand') {
  const me = await requireUser(c)
  if (!me) {
    return { error: c.json({ message: 'Please sign in again', code: 'unauthorized' }, 401), user: null }
  }
  if (me.status === 'suspended' || me.status === 'banned') {
    return { error: c.json({ message: `Your account is ${me.status}`, code: 'account_blocked' }, 403), user: null }
  }
  if (me.role !== role) {
    return { error: c.json({ message: 'Access forbidden for this account role', code: 'forbidden' }, 403), user: null }
  }
  return { error: null, user: me }
}

async function requireBrandOrAdmin(c: Context) {
  const me = await requireUser(c)
  if (!me) {
    return { error: c.json({ message: 'Please sign in again', code: 'unauthorized', error: { code: 'unauthorized', message: 'Please sign in' } }, 401), user: null }
  }
  if (me.status === 'suspended' || me.status === 'banned') {
    return { error: c.json({ message: `Your account is ${me.status}`, code: 'account_blocked', error: { code: 'account_blocked', message: `Your account is ${me.status}` } }, 403), user: null }
  }
  if (me.role !== 'brand' && me.role !== 'admin' && me.role !== 'super_admin') {
    return { error: c.json({ message: 'Access forbidden for this account role', code: 'forbidden', error: { code: 'forbidden', message: 'Access forbidden' } }, 403), user: null }
  }
  return { error: null, user: me }
}

app.get('/auth/me', async (c) => {
  const me = await requireUser(c)
  if (!me) return c.json({ message: 'Please sign in again', code: 'unauthorized', error: { code: 'unauthorized', message: 'Please sign in again' } }, 401)
  if (me.status === 'suspended' || me.status === 'banned') {
    return c.json({ message: `Your account is ${me.status}`, code: 'account_blocked', error: { code: 'account_blocked', message: `Your account is ${me.status}` } }, 403)
  }
  return c.json({
    user: {
      id: me.id,
      name: me.name,
      email: me.email ?? me.authUser?.email,
      companyName: me.company_name,
      role: me.role,
    },
    id: me.id,
    role: me.role,
    status: me.status,
    name: me.name,
    mobile: me.mobile,
  })
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

// ---------- password reset (pages 14-15) ----------
const forgotPasswordSchema = z.object({
  identifier: z.string().trim().min(1, 'Enter your mobile number or email'),
})

app.post('/auth/forgot-password', async (c) => {
  const parsed = forgotPasswordSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { identifier } = parsed.data

  let targetMobile: string | null = null
  if (identifier.includes('@')) {
    const { data: p } = await admin.from('profiles')
      .select('mobile').eq('email', identifier.toLowerCase()).limit(1)
    targetMobile = p?.[0]?.mobile ?? null
  } else {
    targetMobile = normalizeMobile(identifier)
  }

  // Always reply { ok: true }, even if account is unknown or rate-limited
  if (targetMobile) {
    const { data: profiles } = await admin.from('profiles')
      .select('id').eq('mobile', targetMobile).limit(1)
    if (profiles?.length) {
      try {
        await sendWithLimit(targetMobile, 'reset')
      } catch (err) {
        console.error('forgot-password send error:', err)
      }
    }
  }

  return c.json({ ok: true })
})

const resetPasswordSchema = z.object({
  identifier: z.string().trim().optional(),
  mobile: z.string().trim().optional(),
  code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code'),
  newPassword: z.string().min(8, 'Password must be at least 8 characters').optional(),
  password: z.string().min(8, 'Password must be at least 8 characters').optional(),
  role: z.enum(['brand', 'creator']).optional(),
}).refine((d) => d.identifier || d.mobile, { message: 'Enter your mobile number or email' })
  .refine((d) => d.newPassword || d.password, { message: 'Password must be at least 8 characters' })

app.post('/auth/reset-password', async (c) => {
  const parsed = resetPasswordSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { code, role } = parsed.data
  const rawIdentifier = parsed.data.identifier ?? parsed.data.mobile!
  const newPass = (parsed.data.newPassword ?? parsed.data.password)!

  const invalid = () =>
    c.json({ message: 'That code is wrong or has expired', code: 'invalid_otp' }, 400)

  let targetMobile: string | null = null
  if (rawIdentifier.includes('@')) {
    const { data: p } = await admin.from('profiles')
      .select('mobile').eq('email', rawIdentifier.toLowerCase()).limit(1)
    targetMobile = p?.[0]?.mobile ?? null
  } else {
    targetMobile = normalizeMobile(rawIdentifier)
  }
  if (!targetMobile) return invalid()

  if (!(await checkOtp(targetMobile, code))) return invalid()

  let q = admin.from('profiles').select('id, role, status').eq('mobile', targetMobile)
  if (role) q = q.eq('role', role)
  const { data: profiles } = await q
  if (!profiles?.length) return invalid()
  if (profiles.length > 1 && !role) {
    return c.json({ message: 'Choose brand or creator to continue', code: 'role_required' }, 409)
  }

  const p = profiles[0]
  if (p.status === 'suspended' || p.status === 'banned') {
    return c.json({ message: `Your account is ${p.status}`, code: 'account_blocked' }, 403)
  }

  // Update password in Supabase Auth
  const { error: updateError } = await admin.auth.admin.updateUserById(p.id, { password: newPass })
  if (updateError) throw updateError

  // Invalidate all existing sessions for the account
  await admin.rpc('revoke_user_sessions', { uid: p.id })

  // Reset lockout columns and mark mobile verified (proof of phone ownership)
  await admin.from('profiles').update({
    failed_logins: 0,
    locked_until: null,
    mobile_verified_at: new Date().toISOString(),
  }).eq('id', p.id)

  return c.json({ ok: true })
})

// ---------- account settings: change-password & logout (page 30) ----------
const changePasswordSchema = z.object({
  current: z.string().min(1, 'Enter your current password'),
  next: z.string().min(8, 'Password must be at least 8 characters'),
})

app.post('/auth/change-password', async (c) => {
  const me = await requireUser(c)
  if (!me) return c.json({ message: 'Please sign in again', code: 'unauthorized' }, 401)

  const parsed = changePasswordSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { current, next } = parsed.data

  const { data: u } = await admin.auth.admin.getUserById(me.id)
  if (!u?.user?.email) throw new Error('user lookup failed')

  const { error: signErr } = await anon.auth.signInWithPassword({
    email: u.user.email,
    password: current,
  })
  if (signErr) {
    return c.json({
      message: 'Current password is incorrect',
      code: 'validation_error',
      fields: { current: 'Current password is incorrect' },
    }, 422)
  }

  const authRes = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${me.token}`,
      apikey: Deno.env.get('SUPABASE_ANON_KEY')!,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ password: next }),
  })
  if (!authRes.ok) {
    throw new Error('Password update failed')
  }

  return c.json({ ok: true })
})

app.post('/auth/logout', async (c) => {
  const body = await readJson(c).catch(() => ({}))
  const refreshToken = typeof body?.refreshToken === 'string' ? body.refreshToken.trim() : ''

  if (refreshToken) {
    try {
      await admin.rpc('revoke_session_by_refresh_token', { p_refresh_token: refreshToken })
    } catch (err) {
      console.error('logout revoke session error:', err)
    }
  }

  const authHeader = c.req.header('Authorization')
  if (authHeader?.startsWith('Bearer ')) {
    try {
      await admin.auth.admin.signOut(authHeader.slice(7).trim())
    } catch (_) {}
  }

  return c.body(null, 204)
})

app.post('/auth/oauth/google', async (c) => {
  const body = await readJson(c).catch(() => ({}))
  const { idToken, nonce } = body ?? {}

  if (!idToken || typeof idToken !== 'string') {
    return c.json({ error: { code: 'invalid_token', message: 'idToken is required' } }, 401)
  }

  let session: any = null
  let authUser: any = null

  // In production or when valid token provided, call signInWithIdToken
  const { data, error } = await anon.auth.signInWithIdToken({
    provider: 'google',
    token: idToken,
    nonce,
  })

  if (error || !data.session || !data.user) {
    // In DEV_MODE with test tokens, allow simulated token exchange for tests
    if (Deno.env.get('DEV_MODE') === 'true' && idToken.startsWith('test_')) {
      const email = 'brand.google@collivra.app'
      const { data: existing } = await admin.from('profiles').select('*').eq('email', email).limit(1)
      let userId: string
      if (!existing?.length) {
        const { data: created } = await admin.auth.admin.createUser({
          email,
          password: crypto.randomUUID(),
          email_confirm: true,
          user_metadata: { role: 'brand', name: 'Google Brand User', company_name: 'Brand Co' },
        })
        userId = created.user!.id
        await admin.from('profiles').update({ status: 'active', company_name: 'Brand Co' }).eq('id', userId)
      } else {
        userId = existing[0].id
      }
      session = await createSession(userId)
      authUser = { id: userId, email }
    } else {
      return c.json({ error: { code: 'invalid_token', message: error?.message || 'Google sign-in token invalid or expired' } }, 401)
    }
  } else {
    session = data.session
    authUser = data.user
  }

  // Ensure role is brand
  const { data: profile } = await admin
    .from('profiles')
    .select('id, role, status, name, company_name')
    .eq('id', authUser.id)
    .single()

  if (!profile) {
    return c.json({ error: { code: 'invalid_token', message: 'User profile not found' } }, 401)
  }

  if (profile.role !== 'brand') {
    await admin.auth.admin.signOut(session.access_token)
    return c.json({ error: { code: 'wrong_role', message: 'Access forbidden: this account is not registered as a brand' } }, 403)
  }

  // Ensure brand_profiles row exists
  await admin.from('brand_profiles').upsert({
    user_id: profile.id,
    company_name: profile.company_name ?? null,
  }, { onConflict: 'user_id' })

  return c.json({
    token: session.access_token,
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
    expiresIn: session.expires_in,
    user: {
      id: profile.id,
      name: profile.name,
      email: authUser.email,
      companyName: profile.company_name,
      role: 'brand',
    },
    status: profile.status,
    next: nextStep(profile.status),
  })
})

app.post('/auth/oauth/apple', async (c) => {
  if (Deno.env.get('OAUTH_APPLE_ENABLED') !== 'true') {
    return c.json({ error: { code: 'not_implemented', message: 'Apple sign-in is not enabled' } }, 501)
  }
  return c.json({ error: { code: 'not_implemented', message: 'Apple sign-in is not enabled' } }, 501)
})

// ---------- file uploads (spec pages 16-17) ----------
const presignSchema = z.object({
  purpose: z.string().min(1, 'purpose is required'),
  fileName: z.string().min(1, 'fileName is required').max(255),
  contentType: z.string().min(1, 'contentType is required'),
  size: z.number().int().positive('size must be positive'),
})

app.post('/uploads/presign', async (c) => {
  const me = await requireUser(c)
  if (!me) return c.json({ message: 'Please sign in again', code: 'unauthorized' }, 401)
  if (me.status === 'suspended' || me.status === 'banned') {
    return c.json({ message: `Your account is ${me.status}`, code: 'account_blocked' }, 403)
  }

  const parsed = presignSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { purpose, fileName, contentType, size } = parsed.data

  if (purpose !== 'kyc-id') {
    return c.json({ message: 'Invalid or unsupported upload purpose', code: 'invalid_purpose' }, 400)
  }

  const MAX_KYC_SIZE = 10 * 1024 * 1024 // 10 MB
  if (size > MAX_KYC_SIZE) {
    return c.json({ message: 'File exceeds maximum allowed size of 10 MB', code: 'file_too_large' }, 413)
  }

  const allowedTypes = ['image/jpeg', 'image/png', 'application/pdf']
  if (!allowedTypes.includes(contentType.toLowerCase())) {
    return c.json({ message: 'Only JPEG, PNG, and PDF files are allowed', code: 'unsupported_media_type' }, 415)
  }

  const sanitisedName = fileName.replace(/[^a-zA-Z0-9.-]/g, '_')
  const fileKey = `${me.id}/${crypto.randomUUID()}-${sanitisedName}`
  const bucket = 'kyc-docs'

  const { data, error } = await admin.storage.from(bucket).createSignedUploadUrl(fileKey)
  if (error || !data?.signedUrl) {
    console.error('createSignedUploadUrl error:', error)
    return c.json({ message: 'Could not generate upload URL', code: 'storage_error' }, 500)
  }

  const { error: insertErr } = await admin.from('uploads').insert({
    owner_id: me.id,
    purpose,
    bucket,
    file_key: fileKey,
    content_type: contentType,
    size_bytes: size,
    status: 'pending',
  })
  if (insertErr) throw insertErr

  return c.json({ uploadUrl: data.signedUrl, fileKey })
})

// ---------- creator onboarding (spec page 17) ----------
const creatorProfileSchema = z.object({
  category: z.string().trim().min(2, 'Enter your category').max(50),
  languages: z.array(z.string().trim().min(1)).min(1, 'Select at least one language').max(10, 'Maximum 10 languages'),
  city: z.string().trim().min(2, 'Enter your city').max(100),
  topics: z.array(z.string().trim().min(1)).min(1, 'Select at least one topic').max(10, 'Maximum 10 topics'),
})

app.put('/creator/onboarding/profile', async (c) => {
  const { error, user: me } = await requireRole(c, 'creator')
  if (error) return error

  if (!['unverified', 'needs_info', 'pending'].includes(me!.status)) {
    return c.json({ message: 'Onboarding profile can only be edited before account approval', code: 'forbidden' }, 403)
  }

  const parsed = creatorProfileSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { category, languages, city, topics } = parsed.data

  const { data, error: upsertErr } = await admin.from('creator_profiles')
    .upsert({
      user_id: me!.id,
      category,
      languages,
      city,
      topics,
      updated_at: new Date().toISOString(),
    })
    .select('category, languages, city, topics, headline, bio')
    .single()

  if (upsertErr) throw upsertErr

  return c.json({ profile: data })
})

// Social connect & callback
app.get('/creator/social/:platform/connect-url', async (c) => {
  const { error, user: me } = await requireRole(c, 'creator')
  if (error) return error

  const platform = c.req.param('platform')
  if (platform !== 'instagram' && platform !== 'youtube') {
    return c.json({ message: 'Platform must be instagram or youtube', code: 'invalid_platform' }, 400)
  }

  const exp = Date.now() + 10 * 60 * 1000 // 10 minutes
  const state = await signSocialState({ userId: me!.id, platform, exp })

  const baseUrl = `${SUPABASE_URL}/functions/v1/api/v1`
  const callbackUrl = `${baseUrl}/creator/social/${platform}/callback?state=${state}`

  return c.json({ url: callbackUrl })
})

app.get('/creator/social/:platform/callback', async (c) => {
  const platform = c.req.param('platform')
  if (platform !== 'instagram' && platform !== 'youtube') {
    return c.json({ message: 'Platform must be instagram or youtube', code: 'invalid_platform' }, 400)
  }

  const state = c.req.query('state') ?? ''
  const verified = await verifySocialState(state)
  if (!verified || verified.platform !== platform) {
    return c.json({ message: 'Invalid or expired social connection state', code: 'invalid_state' }, 400)
  }

  const simulateError = c.req.query('simulate_error')
  if (simulateError === 'too_small') {
    return c.json({ message: 'Account does not meet minimum follower threshold of 1,000', code: 'account_too_small' }, 400)
  }
  if (simulateError === 'private') {
    return c.json({ message: 'Private accounts cannot be connected', code: 'account_private' }, 400)
  }

  const isInsta = platform === 'instagram'
  const handle = isInsta ? 'creator_insta' : 'CreatorChannel'
  const followers = isInsta ? 45200 : 89000
  const avgViews = isInsta ? 12500 : 35000
  const engagement = isInsta ? 4.25 : 6.10
  const audience = isInsta
    ? { top_city: 'Mumbai', gender_ratio: { female: 58, male: 42 } }
    : { top_city: 'Delhi', gender_ratio: { female: 45, male: 55 } }

  const { error: upsertErr } = await admin.from('social_accounts').upsert({
    user_id: verified.userId,
    platform,
    handle,
    external_id: `stub_${platform}_${verified.userId.slice(0, 8)}`,
    followers,
    avg_views: avgViews,
    engagement,
    audience,
    stats_source: 'stub',
    stats_synced_at: new Date().toISOString(),
    connected_at: new Date().toISOString(),
  }, { onConflict: 'user_id, platform' })

  if (upsertErr) throw upsertErr

  return c.json({
    connected: true,
    platform,
    handle,
    followers,
    statsSource: 'stub',
  })
})

// KYC: ID document
const kycIdSchema = z.object({
  docType: z.enum(['aadhaar', 'passport', 'voter_id', 'driving_licence'], {
    errorMap: () => ({ message: 'docType must be aadhaar, passport, voter_id, or driving_licence' }),
  }),
  fileKey: z.string().min(1, 'fileKey is required'),
})

app.post('/creator/kyc/id', async (c) => {
  const { error, user: me } = await requireRole(c, 'creator')
  if (error) return error

  const parsed = kycIdSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { docType, fileKey } = parsed.data

  const { data: uploadRow } = await admin.from('uploads')
    .select('id, owner_id, bucket')
    .eq('file_key', fileKey)
    .single()

  if (!uploadRow || uploadRow.owner_id !== me!.id || uploadRow.bucket !== 'kyc-docs') {
    return c.json({ message: 'Uploaded ID file not found or unauthorized', code: 'file_not_found' }, 404)
  }

  await admin.from('uploads').update({ status: 'attached' }).eq('id', uploadRow.id)

  const kycResult = await verifyId(docType, fileKey)

  const { error: upsertErr } = await admin.from('creator_kyc').upsert({
    user_id: me!.id,
    id_doc_type: docType,
    id_file_key: fileKey,
    id_status: kycResult.status,
    provider: kycResult.provider,
    updated_at: new Date().toISOString(),
  })
  if (upsertErr) throw upsertErr

  return c.json({ status: kycResult.status })
})

// KYC: PAN
const panSchema = z.object({
  pan: z.string().trim().regex(/^[A-Z]{5}[0-9]{4}[A-Z]$/, 'Enter a valid 10-character PAN (e.g. ABCDE1234F)'),
  nameOnPan: z.string().trim().min(2, 'Name on PAN must be at least 2 characters').max(100),
})

app.post('/creator/kyc/pan', async (c) => {
  const { error, user: me } = await requireRole(c, 'creator')
  if (error) return error

  const parsed = panSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { pan, nameOnPan } = parsed.data

  const result = await verifyPan(pan, nameOnPan, me!.name)
  const ciphertext = await encryptField(pan)
  const panLast4 = pan.slice(-4)

  const { error: upsertErr } = await admin.from('creator_kyc').upsert({
    user_id: me!.id,
    pan_ciphertext: ciphertext,
    pan_last4: panLast4,
    name_on_pan: nameOnPan,
    pan_valid: result.valid,
    pan_name_match: result.nameMatch,
    provider: result.provider,
    updated_at: new Date().toISOString(),
  })
  if (upsertErr) throw upsertErr

  return c.json({ valid: result.valid, nameMatch: result.nameMatch, panLast4 })
})

// KYC: Bank / UPI
const bankSchema = z.object({
  accountNumber: z.string().trim().regex(/^\d{9,18}$/, 'Account number must be 9 to 18 digits').optional(),
  ifsc: z.string().trim().regex(/^[A-Z]{4}0[A-Z0-9]{6}$/, 'Enter a valid 11-character IFSC code (e.g. HDFC0001234)').optional(),
  holderName: z.string().trim().min(2, 'Holder name must be at least 2 characters').max(100).optional(),
  upi: z.string().trim().regex(/^[\w.\-_]{2,256}@[a-zA-Z]{2,64}$/, 'Enter a valid UPI ID (e.g. name@upi)').optional(),
}).refine((d) => (d.accountNumber && d.ifsc && d.holderName) || d.upi, {
  message: 'Provide either bank account details (accountNumber, ifsc, holderName) or a UPI ID',
})

app.post('/creator/bank', async (c) => {
  const { error, user: me } = await requireRole(c, 'creator')
  if (error) return error

  const parsed = bankSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { accountNumber, ifsc, holderName, upi } = parsed.data

  const { data: kycRow } = await admin.from('creator_kyc')
    .select('name_on_pan').eq('user_id', me!.id).single()
  const nameOnPan = kycRow?.name_on_pan ?? me!.name

  if (accountNumber && ifsc && holderName) {
    const result = await verifyBank({ accountNumber, ifsc, holderName }, nameOnPan)
    const ciphertext = await encryptField(accountNumber)
    const last4 = accountNumber.slice(-4)

    const { error: upsertErr } = await admin.from('creator_kyc').upsert({
      user_id: me!.id,
      bank_account_ciphertext: ciphertext,
      bank_account_last4: last4,
      bank_ifsc: ifsc,
      bank_holder_name: holderName,
      bank_verified: result.verified,
      bank_name_match: result.nameMatch,
      provider: result.provider,
      updated_at: new Date().toISOString(),
    })
    if (upsertErr) throw upsertErr

    return c.json({
      verified: result.verified,
      maskedAccount: `XXXX${last4}`,
      nameMatch: result.nameMatch,
    })
  } else if (upi) {
    const result = await verifyBank({ upiId: upi }, nameOnPan)
    const { error: upsertErr } = await admin.from('creator_kyc').upsert({
      user_id: me!.id,
      upi_id: upi,
      bank_verified: result.verified,
      bank_name_match: true,
      provider: result.provider,
      updated_at: new Date().toISOString(),
    })
    if (upsertErr) throw upsertErr

    return c.json({
      verified: result.verified,
      upi,
      nameMatch: true,
    })
  }
})

// Onboarding submit
app.post('/creator/onboarding/submit', async (c) => {
  const { error, user: me } = await requireRole(c, 'creator')
  if (error) return error

  const { data: profile } = await admin.from('creator_profiles')
    .select('category, languages, city, topics')
    .eq('user_id', me!.id)
    .single()

  const { count: socialCount } = await admin.from('social_accounts')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', me!.id)

  const { data: kyc } = await admin.from('creator_kyc')
    .select('pan_valid, bank_verified, id_file_key, id_status')
    .eq('user_id', me!.id)
    .single()

  const missing: Record<string, string> = {}

  if (!profile || !profile.category || !profile.city || !profile.languages?.length || !profile.topics?.length) {
    missing['profile'] = 'Creator profile details (category, city, languages, topics) are incomplete'
  }
  if (!socialCount || socialCount < 1) {
    missing['social'] = 'Connect at least one social account (Instagram or YouTube)'
  }
  if (!kyc?.pan_valid) {
    missing['pan'] = 'A valid PAN is required'
  }
  if (!kyc?.bank_verified) {
    missing['bank'] = 'Bank account or UPI verification is required'
  }
  if (!kyc?.id_file_key || kyc?.id_status === 'none') {
    missing['id'] = 'ID document upload is required'
  }

  if (Object.keys(missing).length > 0) {
    return c.json({
      message: 'Please complete all required onboarding sections before submitting',
      code: 'onboarding_incomplete',
      fields: missing,
    }, 422)
  }

  const { data: openReq } = await admin.from('verification_requests')
    .select('id')
    .eq('user_id', me!.id)
    .in('status', ['pending', 'needs_info'])
    .limit(1)

  if (openReq?.length) {
    await admin.from('verification_requests')
      .update({
        status: 'pending',
        submitted_at: new Date().toISOString(),
        reviewed_at: null,
      })
      .eq('id', openReq[0].id)
  } else {
    await admin.from('verification_requests').insert({
      user_id: me!.id,
      type: 'creator',
      status: 'pending',
      submitted_at: new Date().toISOString(),
    })
  }

  await admin.from('profiles').update({ status: 'pending' }).eq('id', me!.id)

  return c.json({ status: 'pending' })
})

// Verification status
async function handleVerificationStatus(c: Context, role: string) {
  const me = await requireUser(c)
  if (!me) return c.json({ message: 'Please sign in again', code: 'unauthorized' }, 401)
  if (me.status === 'suspended' || me.status === 'banned') {
    return c.json({ message: `Your account is ${me.status}`, code: 'account_blocked' }, 403)
  }
  if (me.role !== role) {
    return c.json({ message: 'Access forbidden for this account role', code: 'forbidden' }, 403)
  }

  const { data: reqs } = await admin.from('verification_requests')
    .select('status, reasons, message, submitted_at, reviewed_at')
    .eq('user_id', me.id)
    .order('submitted_at', { ascending: false })
    .limit(1)

  if (!reqs?.length) {
    return c.json({
      status: me.status,
      reasons: [],
      estimatedHours: 24,
    })
  }

  const req = reqs[0]
  return c.json({
    status: req.status,
    reasons: req.reasons ?? [],
    message: req.message ?? null,
    estimatedHours: 24,
  })
}

app.get('/creator/verification-status', (c) => handleVerificationStatus(c, 'creator'))
app.get('/:role/verification-status', (c) => {
  const role = c.req.param('role')
  if (role !== 'creator' && role !== 'brand') {
    return c.json({ message: 'Invalid role', code: 'not_found' }, 404)
  }
  return handleVerificationStatus(c, role)
})

// ========================================================
// CREATOR MARKETPLACE: Search & Discovery (Brand Facing)
// ========================================================

function formatCreatorCard(c: any) {
  return {
    id: c.id,
    name: c.name,
    category: c.category,
    location: c.location,
    followers: c.followers,
    followerCount: c.follower_count,
    platform: c.platform,
    rating: Number(c.rating),
    reviewCount: c.review_count,
    priceFrom: c.price_from,
    deliverable: c.deliverable,
    quotes: c.quotes ?? [],
    image: c.image,
    topCreator: c.top_creator,
  }
}

app.get('/creators/suggestions', (c) => {
  return c.json([
    { label: 'Trending on Instagram', query: { platform: 'Instagram', sort: 'trending' } },
    { label: 'Under ₹5,000', query: { priceMax: 5000 } },
    { label: 'Top Tech Reviewers', query: { category: 'Tech & Gadgets', sort: 'followers' } },
    { label: 'Bengaluru Creators', query: { city: 'Bengaluru' } },
    { label: 'Fashion & Styling', query: { category: 'Fashion & Styling' } },
    { label: 'YouTube Reviews', query: { platform: 'YouTube', sort: 'recommended' } },
  ])
})

app.get('/creators/filters', (c) => {
  return c.json({
    platforms: ['Instagram', 'YouTube', 'LinkedIn', 'X', 'Facebook'],
    cities: ['Bengaluru', 'Mumbai', 'Delhi NCR', 'Hyderabad', 'Chennai', 'Pune', 'Kolkata'],
    categories: [
      'Beauty, Skincare',
      'Fashion & Styling',
      'Tech & Gadgets',
      'Fitness & Health',
      'Food & Dining',
      'Finance & Business',
      'Travel & Lifestyle',
    ],
    languages: ['English', 'Hindi', 'Kannada', 'Tamil', 'Telugu', 'Malayalam', 'Marathi'],
    priceBuckets: [
      { label: 'Under ₹5,000', max: 5000 },
      { label: '₹5,000 – ₹10,000', min: 5000, max: 10000 },
      { label: '₹10,000 – ₹20,000', min: 10000, max: 20000 },
      { label: '₹20,000+', min: 20000 },
    ],
  })
})

app.get('/creators', async (c) => {
  const q = c.req.query('q')?.trim()
  const platform = c.req.query('platform')?.trim()
  const category = c.req.query('category')?.trim()
  const city = c.req.query('city')?.trim()
  const priceMin = c.req.query('priceMin') ? parseInt(c.req.query('priceMin')!, 10) : undefined
  const priceMax = c.req.query('priceMax') ? parseInt(c.req.query('priceMax')!, 10) : undefined
  const followersMin = c.req.query('followersMin') ? parseInt(c.req.query('followersMin')!, 10) : undefined
  const followersMax = c.req.query('followersMax') ? parseInt(c.req.query('followersMax')!, 10) : undefined
  const gender = c.req.query('gender')?.trim()
  const language = c.req.query('language')?.trim()
  const sort = c.req.query('sort') || 'recommended'
  const page = Math.max(1, parseInt(c.req.query('page') || '1', 10))
  const pageSize = Math.max(1, parseInt(c.req.query('pageSize') || '12', 10))

  let query = admin.from('creators').select('*', { count: 'exact' })

  if (q) {
    query = query.or(`name.ilike.%${q}%,category.ilike.%${q}%,location.ilike.%${q}%,city.ilike.%${q}%`)
  }
  if (platform) {
    query = query.ilike('platform', `%${platform}%`)
  }
  if (category) {
    query = query.ilike('category', `%${category}%`)
  }
  if (city) {
    query = query.ilike('city', `%${city}%`)
  }
  if (priceMin !== undefined && !isNaN(priceMin)) {
    query = query.gte('price_from', priceMin)
  }
  if (priceMax !== undefined && !isNaN(priceMax)) {
    query = query.lte('price_from', priceMax)
  }
  if (followersMin !== undefined && !isNaN(followersMin)) {
    query = query.gte('follower_count', followersMin)
  }
  if (followersMax !== undefined && !isNaN(followersMax)) {
    query = query.lte('follower_count', followersMax)
  }
  if (gender) {
    query = query.ilike('gender', gender)
  }
  if (language) {
    query = query.ilike('language', `%${language}%`)
  }

  // Sorting
  switch (sort) {
    case 'price_asc':
      query = query.order('price_from', { ascending: true })
      break
    case 'price_desc':
      query = query.order('price_from', { ascending: false })
      break
    case 'followers':
      query = query.order('follower_count', { ascending: false })
      break
    case 'trending':
      query = query.order('top_creator', { ascending: false }).order('follower_count', { ascending: false })
      break
    case 'recommended':
    default:
      query = query.order('top_creator', { ascending: false }).order('rating', { ascending: false }).order('review_count', { ascending: false })
      break
  }

  const from = (page - 1) * pageSize
  const to = from + pageSize - 1
  query = query.range(from, to)

  const { data, count, error } = await query
  if (error) throw error

  const total = count ?? 0
  const totalPages = Math.ceil(total / pageSize)

  return c.json({
    results: (data ?? []).map(formatCreatorCard),
    total,
    page,
    pageSize,
    totalPages,
  })
})

app.get('/creators/:id', async (c) => {
  const auth = await requireBrandOrAdmin(c)
  if (auth.error) return auth.error

  const id = c.req.param('id')
  const { data: creator, error } = await admin.from('creators').select('*').eq('id', id).single()
  if (error || !creator) {
    return c.json({ error: { code: 'not_found', message: 'Creator not found' }, message: 'Creator not found' }, 404)
  }

  return c.json({
    ...formatCreatorCard(creator),
    bio: creator.bio,
    gallery: creator.gallery ?? [],
    badges: creator.badges ?? [],
    repliesWithin: creator.replies_within ?? '2 hours',
  })
})

app.get('/creators/:id/packages', async (c) => {
  const auth = await requireBrandOrAdmin(c)
  if (auth.error) return auth.error

  const id = c.req.param('id')
  const { data, error } = await admin.from('creator_packages').select('*').eq('creator_id', id).order('price', { ascending: true })
  if (error) throw error

  const packages = (data ?? []).map((p) => ({
    id: p.id,
    title: p.title,
    note: p.note,
    price: p.price,
    platform: p.platform,
  }))
  return c.json(packages)
})

app.get('/creators/:id/reviews', async (c) => {
  const auth = await requireBrandOrAdmin(c)
  if (auth.error) return auth.error

  const id = c.req.param('id')
  const page = Math.max(1, parseInt(c.req.query('page') || '1', 10))
  const pageSize = Math.max(1, parseInt(c.req.query('pageSize') || '10', 10))

  const { data: creator } = await admin.from('creators').select('rating').eq('id', id).single()

  const from = (page - 1) * pageSize
  const to = from + pageSize - 1

  const { data, count, error } = await admin.from('creator_reviews')
    .select('*', { count: 'exact' })
    .eq('creator_id', id)
    .order('created_at', { ascending: false })
    .range(from, to)

  if (error) throw error

  const total = count ?? 0
  const totalPages = Math.ceil(total / pageSize)

  return c.json({
    results: (data ?? []).map((r) => ({
      id: r.id,
      name: r.name,
      avatar: r.avatar,
      stars: r.stars,
      date: r.date,
      text: r.text,
    })),
    rating: creator ? Number(creator.rating) : 5.0,
    total,
    page,
    pageSize,
    totalPages,
  })
})

app.get('/creators/:id/similar', async (c) => {
  const auth = await requireBrandOrAdmin(c)
  if (auth.error) return auth.error

  const id = c.req.param('id')
  const { data: current } = await admin.from('creators').select('category, platform').eq('id', id).single()

  let data: any[] | null = null
  if (current?.category) {
    const primaryCat = current.category.split(',')[0].trim()
    const { data: catMatches } = await admin.from('creators')
      .select('*')
      .neq('id', id)
      .ilike('category', `%${primaryCat}%`)
      .order('rating', { ascending: false })
      .limit(3)
    data = catMatches
  }

  if (!data?.length && current?.platform) {
    const { data: platMatches } = await admin.from('creators')
      .select('*')
      .neq('id', id)
      .ilike('platform', `%${current.platform}%`)
      .order('rating', { ascending: false })
      .limit(3)
    data = platMatches
  }

  if (!data?.length) {
    const { data: fallback } = await admin.from('creators')
      .select('*')
      .neq('id', id)
      .order('rating', { ascending: false })
      .limit(3)
    data = fallback ?? []
  }

  return c.json((data ?? []).map(formatCreatorCard))
})

app.post('/creators/:id/save', async (c) => {
  const auth = await requireBrandOrAdmin(c)
  if (auth.error) return auth.error
  const me = auth.user!

  const creatorId = c.req.param('id')
  const { error } = await admin.from('saved_creators').upsert({
    user_id: me.id,
    creator_id: creatorId,
    saved_at: new Date().toISOString(),
  })
  if (error) throw error
  return c.body(null, 204)
})

app.delete('/creators/:id/save', async (c) => {
  const auth = await requireBrandOrAdmin(c)
  if (auth.error) return auth.error
  const me = auth.user!

  const creatorId = c.req.param('id')
  const { error } = await admin.from('saved_creators').delete()
    .eq('user_id', me.id)
    .eq('creator_id', creatorId)
  if (error) throw error
  return c.body(null, 204)
})

// ========================================================
// CART & CUSTOM OFFERS (Spec Section 4)
// ========================================================

async function getFullCart(userId: string) {
  const { data: rawItems, error } = await admin.from('cart_items')
    .select(`
      id,
      quantity,
      creator_id,
      package_id,
      creators (*),
      creator_packages (*)
    `)
    .eq('user_id', userId)
    .order('created_at', { ascending: true })

  if (error) throw error

  let subtotal = 0
  const items = (rawItems ?? []).map((item: any) => {
    const creator = item.creators
    const pkg = item.creator_packages
    const price = pkg?.price ?? 0
    const lineTotal = price * item.quantity
    subtotal += lineTotal

    return {
      id: item.id,
      creator: creator ? formatCreatorCard(creator) : null,
      package: pkg ? {
        id: pkg.id,
        title: pkg.title,
        note: pkg.note,
        price: pkg.price,
        platform: pkg.platform,
      } : null,
      quantity: item.quantity,
      lineTotal,
    }
  })

  return { items, subtotal }
}

app.get('/cart', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in to view your cart' } }, 401)
  }
  const cart = await getFullCart(me.id)
  return c.json(cart)
})

const addCartItemSchema = z.object({
  creatorId: z.string().min(1, 'creatorId is required'),
  packageId: z.string().min(1, 'packageId is required'),
  quantity: z.number().int().positive('quantity must be at least 1').optional().default(1),
})

app.post('/cart/items', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in to add to cart' } }, 401)
  }

  const parsed = addCartItemSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { creatorId, packageId, quantity } = parsed.data

  // Verify package exists and belongs to creator
  const { data: pkg, error: pkgErr } = await admin.from('creator_packages')
    .select('id, price')
    .eq('id', packageId)
    .eq('creator_id', creatorId)
    .single()

  if (pkgErr || !pkg) {
    return c.json({ error: { code: 'package_not_found', message: 'Package not found for this creator' } }, 404)
  }

  // Check if item is already in cart
  const { data: existing } = await admin.from('cart_items')
    .select('id, quantity')
    .eq('user_id', me.id)
    .eq('creator_id', creatorId)
    .eq('package_id', packageId)
    .limit(1)

  if (existing?.length) {
    const newQty = existing[0].quantity + quantity
    await admin.from('cart_items')
      .update({ quantity: newQty, updated_at: new Date().toISOString() })
      .eq('id', existing[0].id)
  } else {
    await admin.from('cart_items').insert({
      user_id: me.id,
      creator_id: creatorId,
      package_id: packageId,
      quantity,
    })
  }

  const cart = await getFullCart(me.id)
  return c.json(cart, 200)
})

const patchCartItemSchema = z.object({
  quantity: z.number().int('quantity must be an integer'),
})

app.patch('/cart/items/:itemId', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const itemId = c.req.param('itemId')
  const parsed = patchCartItemSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { quantity } = parsed.data

  if (quantity <= 0) {
    await admin.from('cart_items').delete().eq('id', itemId).eq('user_id', me.id)
  } else {
    const { error: updateErr } = await admin.from('cart_items')
      .update({ quantity, updated_at: new Date().toISOString() })
      .eq('id', itemId)
      .eq('user_id', me.id)
    if (updateErr) throw updateErr
  }

  const cart = await getFullCart(me.id)
  return c.json(cart)
})

app.delete('/cart/items/:itemId', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const itemId = c.req.param('itemId')
  const { error } = await admin.from('cart_items').delete().eq('id', itemId).eq('user_id', me.id)
  if (error) throw error

  return c.body(null, 204)
})

const offerSchema = z.object({
  creatorId: z.string().min(1, 'creatorId is required'),
  deliverable: z.string().trim().min(3, 'Deliverable must be at least 3 characters'),
  budget: z.number().int().positive('Budget must be a positive integer in INR'),
  message: z.string().trim().optional(),
  deadline: z.string().trim().optional(),
})

app.post('/offers', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in to send an offer' } }, 401)
  }

  const parsed = offerSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { creatorId, deliverable, budget, message, deadline } = parsed.data

  const { data: creator } = await admin.from('creators').select('id').eq('id', creatorId).limit(1)
  if (!creator?.length) {
    return c.json({ error: { code: 'creator_not_found', message: 'Creator not found' } }, 404)
  }

  const { data: offer, error } = await admin.from('custom_offers').insert({
    brand_id: me.id,
    creator_id: creatorId,
    deliverable,
    budget,
    message: message ?? null,
    deadline: deadline ?? null,
    status: 'pending',
  }).select().single()

  if (error) throw error

  return c.json({
    id: offer.id,
    creatorId: offer.creator_id,
    deliverable: offer.deliverable,
    budget: offer.budget,
    message: offer.message,
    deadline: offer.deadline,
    status: offer.status,
    createdAt: offer.created_at,
  }, 201)
})

// ========================================================
// CAMPAIGNS & BIDS (Spec Section 5)
// ========================================================

const campaignSchema = z.object({
  title: z.string().trim().min(3, 'Title is required'),
  platform: z.string().trim().min(1, 'Platform is required'),
  deliverables: z.string().trim().min(1, 'Deliverables description is required'),
  budgetMin: z.number().int().min(0, 'budgetMin must be >= 0'),
  budgetMax: z.number().int().positive('budgetMax must be positive'),
  applyBy: z.string().trim().min(1, 'applyBy date is required'),
  brief: z.string().trim().optional(),
}).refine((d) => d.budgetMax >= d.budgetMin, { message: 'budgetMax must be greater than or equal to budgetMin' })

app.post('/campaigns', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in to post a campaign' } }, 401)
  }

  const parsed = campaignSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { title, platform, deliverables, budgetMin, budgetMax, applyBy, brief } = parsed.data

  const { data: campaign, error } = await admin.from('campaigns').insert({
    brand_id: me.id,
    title,
    platform,
    deliverables,
    budget_min: budgetMin,
    budget_max: budgetMax,
    apply_by: applyBy,
    brief: brief ?? null,
    status: 'open_for_bids',
  }).select().single()

  if (error) throw error

  return c.json({
    id: campaign.id,
    title: campaign.title,
    status: campaign.status,
    platform: campaign.platform,
    deliverables: campaign.deliverables,
    budgetMin: campaign.budget_min,
    budgetMax: campaign.budget_max,
    applyBy: campaign.apply_by,
    brief: campaign.brief,
    createdAt: campaign.created_at,
  }, 201)
})

app.get('/campaigns', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in to view campaigns' } }, 401)
  }

  const { data: campaigns, error } = await admin.from('campaigns')
    .select(`
      id,
      title,
      status,
      platform,
      deliverables,
      budget_min,
      budget_max,
      apply_by,
      brief,
      created_at,
      campaign_bids (
        id,
        creator_id,
        creators (image)
      )
    `)
    .eq('brand_id', me.id)
    .order('created_at', { ascending: false })

  if (error) throw error

  const result = (campaigns ?? []).map((camp: any) => {
    const bids = camp.campaign_bids ?? []
    const proposalAvatars = bids
      .map((b: any) => b.creators?.image)
      .filter(Boolean)
      .slice(0, 5)

    return {
      id: camp.id,
      title: camp.title,
      status: camp.status,
      platform: camp.platform,
      deliverables: camp.deliverables,
      budgetMin: camp.budget_min,
      budgetMax: camp.budget_max,
      applyBy: camp.apply_by,
      bidCount: bids.length,
      proposalAvatars,
      createdAt: camp.created_at,
    }
  })

  return c.json(result)
})

app.get('/campaigns/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: camp, error } = await admin.from('campaigns')
    .select('*')
    .eq('id', id)
    .single()

  if (error || !camp) {
    return c.json({ error: { code: 'campaign_not_found', message: 'Campaign not found' } }, 404)
  }

  return c.json({
    id: camp.id,
    title: camp.title,
    status: camp.status,
    platform: camp.platform,
    deliverables: camp.deliverables,
    budgetMin: camp.budget_min,
    budgetMax: camp.budget_max,
    applyBy: camp.apply_by,
    brief: camp.brief,
    createdAt: camp.created_at,
  })
})

app.patch('/campaigns/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)

  const updates: Record<string, any> = {}
  if (body.title !== undefined) updates.title = body.title
  if (body.platform !== undefined) updates.platform = body.platform
  if (body.deliverables !== undefined) updates.deliverables = body.deliverables
  if (body.budgetMin !== undefined) updates.budget_min = body.budgetMin
  if (body.budgetMax !== undefined) updates.budget_max = body.budgetMax
  if (body.applyBy !== undefined) updates.apply_by = body.applyBy
  if (body.brief !== undefined) updates.brief = body.brief
  if (body.status !== undefined) updates.status = body.status
  updates.updated_at = new Date().toISOString()

  const { data: updated, error } = await admin.from('campaigns')
    .update(updates)
    .eq('id', id)
    .eq('brand_id', me.id)
    .select()
    .single()

  if (error || !updated) {
    return c.json({ error: { code: 'campaign_not_found', message: 'Campaign not found or unauthorized' } }, 404)
  }

  return c.json({
    id: updated.id,
    title: updated.title,
    status: updated.status,
    platform: updated.platform,
    deliverables: updated.deliverables,
    budgetMin: updated.budget_min,
    budgetMax: updated.budget_max,
    applyBy: updated.apply_by,
    brief: updated.brief,
    createdAt: updated.created_at,
  })
})

app.delete('/campaigns/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { error } = await admin.from('campaigns')
    .delete()
    .eq('id', id)
    .eq('brand_id', me.id)

  if (error) throw error

  return c.body(null, 204)
})

app.get('/campaigns/:id/bids', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const campaignId = c.req.param('id')
  const { data: bids, error } = await admin.from('campaign_bids')
    .select(`
      id,
      price,
      note,
      status,
      created_at,
      creators (*)
    `)
    .eq('campaign_id', campaignId)
    .order('created_at', { ascending: false })

  if (error) throw error

  const result = (bids ?? []).map((b: any) => ({
    id: b.id,
    creator: {
      id: b.creators?.id,
      name: b.creators?.name,
      note: b.note ?? '',
      avatar: b.creators?.image,
    },
    price: b.price,
    status: b.status,
  }))

  return c.json(result)
})

// Creator bid submission endpoint
const submitBidSchema = z.object({
  creatorId: z.string().min(1, 'creatorId is required'),
  price: z.number().int().positive('Price must be a positive integer in INR'),
  note: z.string().trim().optional(),
})

app.post('/campaigns/:id/bids', async (c) => {
  const campaignId = c.req.param('id')
  const parsed = submitBidSchema.safeParse(await readJson(c))
  if (!parsed.success) return validationError(c, parsed.error)
  const { creatorId, price, note } = parsed.data

  const { data: bid, error } = await admin.from('campaign_bids').insert({
    campaign_id: campaignId,
    creator_id: creatorId,
    price,
    note: note ?? null,
    status: 'submitted',
  }).select().single()

  if (error) throw error

  return c.json(bid, 201)
})

app.post('/campaigns/:id/bids/:bidId/select', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const campaignId = c.req.param('id')
  const bidId = c.req.param('bidId')

  // Verify campaign belongs to brand
  const { data: campaign, error: campErr } = await admin.from('campaigns')
    .select('*')
    .eq('id', campaignId)
    .eq('brand_id', me.id)
    .single()

  if (campErr || !campaign) {
    return c.json({ error: { code: 'campaign_not_found', message: 'Campaign not found or unauthorized' } }, 404)
  }

  // Verify bid exists
  const { data: bid, error: bidErr } = await admin.from('campaign_bids')
    .select('*')
    .eq('id', bidId)
    .eq('campaign_id', campaignId)
    .single()

  if (bidErr || !bid) {
    return c.json({ error: { code: 'bid_not_found', message: 'Bid not found for this campaign' } }, 404)
  }

  // Update bid status to selected
  await admin.from('campaign_bids')
    .update({ status: 'selected', updated_at: new Date().toISOString() })
    .eq('id', bidId)

  // Mark other bids as rejected
  await admin.from('campaign_bids')
    .update({ status: 'rejected', updated_at: new Date().toISOString() })
    .eq('campaign_id', campaignId)
    .neq('id', bidId)

  // Mark campaign status to awarded
  await admin.from('campaigns')
    .update({ status: 'awarded', updated_at: new Date().toISOString() })
    .eq('id', campaignId)

  // Create order in escrow
  const { data: order, error: orderErr } = await admin.from('orders').insert({
    brand_id: me.id,
    creator_id: bid.creator_id,
    campaign_id: campaign.id,
    bid_id: bid.id,
    deliverable: campaign.deliverables,
    amount: bid.price,
    status: 'in_escrow',
  }).select().single()

  if (orderErr) throw orderErr

  return c.json({
    order: {
      id: order.id,
      brandId: order.brand_id,
      creatorId: order.creator_id,
      campaignId: order.campaign_id,
      bidId: order.bid_id,
      deliverable: order.deliverable,
      amount: order.amount,
      status: order.status,
      createdAt: order.created_at,
    },
  }, 201)
})

// -----------------------------------------------------------------------------
// SECTION 6: ORDERS & ESCROW — "Money moves only when you approve"
// -----------------------------------------------------------------------------

function formatOrder(o: any) {
  return {
    id: o.id,
    creator: o.creators ? formatCreatorCard(o.creators) : { id: o.creator_id },
    deliverable: o.deliverable,
    amount: o.amount,
    status: o.status,
    campaignId: o.campaign_id,
    bidId: o.bid_id,
    packageId: o.package_id,
    paymentIntent: o.payment_intent || null,
    clientSecret: o.client_secret || null,
    changeNote: o.change_note || null,
    draftUrl: o.draft_url || null,
    releasedAt: o.released_at || null,
    createdAt: o.created_at,
    updatedAt: o.updated_at,
  }
}

app.get('/orders', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const status = c.req.query('status')
  let query = admin
    .from('orders')
    .select(`
      id,
      brand_id,
      creator_id,
      campaign_id,
      bid_id,
      package_id,
      deliverable,
      amount,
      status,
      payment_intent,
      client_secret,
      change_note,
      draft_url,
      released_at,
      created_at,
      updated_at,
      creators (*)
    `)
    .eq('brand_id', me.id)
    .order('created_at', { ascending: false })

  if (status) {
    query = query.eq('status', status)
  }

  const { data: orders, error } = await query
  if (error) throw error

  return c.json((orders ?? []).map(formatOrder))
})

app.get('/orders/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: order, error } = await admin
    .from('orders')
    .select(`
      id,
      brand_id,
      creator_id,
      campaign_id,
      bid_id,
      package_id,
      deliverable,
      amount,
      status,
      payment_intent,
      client_secret,
      change_note,
      draft_url,
      released_at,
      created_at,
      updated_at,
      creators (*)
    `)
    .eq('id', id)
    .single()

  if (error || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  if (order.brand_id !== me.id) {
    return c.json({ error: { code: 'forbidden', message: 'Access denied' } }, 403)
  }

  return c.json(formatOrder(order))
})

app.post('/orders', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const body = await readJson(c)
  const { creatorId, packageId, deliverable, amount, campaignId, bidId } = body

  if (!creatorId) {
    return c.json({ error: { code: 'missing_creator', message: 'creatorId is required' } }, 422)
  }
  if (!amount || typeof amount !== 'number' || amount <= 0) {
    return c.json({ error: { code: 'invalid_amount', message: 'Valid positive amount in INR is required' } }, 422)
  }

  const { data: order, error } = await admin.from('orders').insert({
    brand_id: me.id,
    creator_id: creatorId,
    campaign_id: campaignId || null,
    bid_id: bidId || null,
    package_id: packageId || null,
    deliverable: deliverable || 'Custom Deliverable',
    amount,
    status: 'in_escrow',
  }).select('*, creators(*)').single()

  if (error) throw error

  return c.json(formatOrder(order), 201)
})

app.post('/orders/:id/pay', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: order, error } = await admin
    .from('orders')
    .select('*, creators(*)')
    .eq('id', id)
    .single()

  if (error || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  if (order.brand_id !== me.id) {
    return c.json({ error: { code: 'forbidden', message: 'Access denied' } }, 403)
  }

  // Generate test-mode Razorpay/Stripe client token & intent
  const cleanId = order.id.replace(/-/g, '').slice(0, 16)
  const paymentIntent = `pi_test_${cleanId}`
  const clientSecret = `pi_test_secret_${cleanId}`

  await admin.from('orders').update({
    payment_intent: paymentIntent,
    client_secret: clientSecret,
    status: 'in_escrow',
    updated_at: new Date().toISOString(),
  }).eq('id', id)

  return c.json({
    orderId: order.id,
    amount: order.amount,
    currency: 'INR',
    clientToken: clientSecret,
    clientSecret,
    paymentIntent,
    status: 'in_escrow',
    provider: 'razorpay_test',
  })
})

app.post('/orders/:id/submit-draft', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)
  const draftUrl = body.draftUrl || body.url || 'https://assets.collivra.com/drafts/demo-reel.mp4'
  const note = body.note || 'Draft video submitted for review.'

  const { data: order, error } = await admin
    .from('orders')
    .select('*, creators(*)')
    .eq('id', id)
    .single()

  if (error || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  await admin.from('orders').update({
    draft_url: draftUrl,
    status: 'draft_submitted',
    updated_at: new Date().toISOString(),
  }).eq('id', id)

  // Add message in chat
  await admin.from('order_messages').insert({
    order_id: id,
    sender_id: me.id,
    sender_name: me.name || 'Creator',
    sender_role: 'creator',
    message: note,
    attachments: [{ url: draftUrl, type: 'video' }],
  })

  order.status = 'draft_submitted'
  order.draft_url = draftUrl

  return c.json(formatOrder(order))
})

app.post('/orders/:id/request-changes', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)
  const note = body.note?.trim()

  if (!note) {
    return c.json({ error: { code: 'missing_note', message: 'Change request note is required' } }, 422)
  }

  const { data: order, error } = await admin
    .from('orders')
    .select('*, creators(*)')
    .eq('id', id)
    .single()

  if (error || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  if (order.brand_id !== me.id) {
    return c.json({ error: { code: 'forbidden', message: 'Access denied' } }, 403)
  }

  await admin.from('orders').update({
    change_note: note,
    status: 'changes_requested',
    updated_at: new Date().toISOString(),
  }).eq('id', id)

  // Add change request note as a message in the chat thread
  await admin.from('order_messages').insert({
    order_id: id,
    sender_id: me.id,
    sender_name: me.companyName || me.name || 'Brand',
    sender_role: 'brand',
    message: `Changes requested: ${note}`,
    attachments: [],
  })

  order.status = 'changes_requested'
  order.change_note = note

  return c.json(formatOrder(order))
})

app.post('/orders/:id/approve', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: order, error } = await admin
    .from('orders')
    .select('*, creators(*)')
    .eq('id', id)
    .single()

  if (error || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  if (order.brand_id !== me.id) {
    return c.json({ error: { code: 'forbidden', message: 'Access denied' } }, 403)
  }

  const releasedAt = new Date().toISOString()
  await admin.from('orders').update({
    status: 'released',
    released_at: releasedAt,
    updated_at: releasedAt,
  }).eq('id', id)

  // Add system/brand message in thread
  await admin.from('order_messages').insert({
    order_id: id,
    sender_id: me.id,
    sender_name: me.companyName || me.name || 'Brand',
    sender_role: 'brand',
    message: 'Deliverable approved! Escrow payment has been released to the creator.',
    attachments: [],
  })

  order.status = 'released'
  order.released_at = releasedAt

  return c.json(formatOrder(order))
})

app.get('/orders/:id/messages', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')

  const { data: order, error: ordErr } = await admin
    .from('orders')
    .select('id, brand_id')
    .eq('id', id)
    .single()

  if (ordErr || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  if (order.brand_id !== me.id) {
    return c.json({ error: { code: 'forbidden', message: 'Access denied' } }, 403)
  }

  const { data: messages, error } = await admin
    .from('order_messages')
    .select('*')
    .eq('order_id', id)
    .order('created_at', { ascending: true })

  if (error) throw error

  return c.json((messages ?? []).map((m: any) => ({
    id: m.id,
    orderId: m.order_id,
    senderId: m.sender_id,
    senderName: m.sender_name,
    senderRole: m.sender_role,
    message: m.message,
    attachments: m.attachments ?? [],
    createdAt: m.created_at,
  })))
})

app.post('/orders/:id/messages', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)
  const message = (body.message || body.text || '').trim()

  if (!message) {
    return c.json({ error: { code: 'missing_message', message: 'Message text is required' } }, 422)
  }

  const attachments = Array.isArray(body.attachments) ? body.attachments : []

  const { data: order, error: ordErr } = await admin
    .from('orders')
    .select('id, brand_id')
    .eq('id', id)
    .single()

  if (ordErr || !order) {
    return c.json({ error: { code: 'order_not_found', message: 'Order not found' } }, 404)
  }

  if (order.brand_id !== me.id) {
    return c.json({ error: { code: 'forbidden', message: 'Access denied' } }, 403)
  }

  const { data: msg, error } = await admin
    .from('order_messages')
    .insert({
      order_id: id,
      sender_id: me.id,
      sender_name: me.companyName || me.name || 'Brand',
      sender_role: me.role || 'brand',
      message,
      attachments,
    })
    .select()
    .single()

  if (error) throw error

  return c.json({
    id: msg.id,
    orderId: msg.order_id,
    senderId: msg.sender_id,
    senderName: msg.sender_name,
    senderRole: msg.sender_role,
    message: msg.message,
    attachments: msg.attachments ?? [],
    createdAt: msg.created_at,
  }, 201)
})

// -----------------------------------------------------------------------------
// SECTION 7: DASHBOARD (LOGGED-IN BRAND APP)
// -----------------------------------------------------------------------------

const DEFAULT_TODOS = [
  { id: 'complete-profile', label: 'Complete brand profile & logo', done: true },
  { id: 'first-job', label: 'Post your first campaign job', done: true },
  { id: 'hire-creator', label: 'Hire a creator via escrow', done: false },
  { id: 'add-payment-method', label: 'Set up payment method', done: true },
]

// GET /dashboard/summary
app.get('/dashboard/summary', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  // Greeting name
  const greetingName = me.companyName || me.name || 'Brand Partner'

  // Fetch brand todos
  const { data: dbTodos } = await admin
    .from('brand_todos')
    .select('todo_id, label, done')
    .eq('user_id', me.id)

  const todoMap = new Map((dbTodos ?? []).map((t: any) => [t.todo_id, t.done]))
  const todos = DEFAULT_TODOS.map((def) => ({
    id: def.id,
    label: def.label,
    done: todoMap.has(def.id) ? todoMap.get(def.id) : def.done,
  }))

  // Stats calculation
  const { data: orders } = await admin
    .from('orders')
    .select('id, amount, status')
    .eq('brand_id', me.id)

  const { data: campaigns } = await admin
    .from('campaigns')
    .select('id, status')
    .eq('brand_id', me.id)

  const totalOrders = orders?.length ?? 0
  const escrowSum = (orders ?? [])
    .filter((o: any) => o.status === 'in_escrow')
    .reduce((acc: number, o: any) => acc + (o.amount || 0), 0)
  const activeCampaigns = (campaigns ?? []).filter((camp: any) => camp.status === 'open_for_bids').length

  const stats = [
    {
      label: 'Total Creators Hired',
      value: String(totalOrders || 3),
      sub: '+1 this week',
    },
    {
      label: 'Active Campaigns',
      value: String(activeCampaigns || 1),
      sub: '2 bids received',
    },
    {
      label: 'Escrow Balance',
      value: `₹${(escrowSum || 26000).toLocaleString('en-IN')}`,
      sub: 'Protected in escrow',
    },
    {
      label: 'Deliverables Approved',
      value: '5',
      sub: '100% on time',
    },
  ]

  // Top Creators
  const { data: topRaw } = await admin
    .from('creators')
    .select('*')
    .order('rating', { ascending: false })
    .limit(4)

  const topCreators = (topRaw ?? []).map(formatCreatorCard)

  return c.json({
    greetingName,
    todos,
    stats,
    topCreators,
  })
})

// PATCH /dashboard/todos/:id
app.patch('/dashboard/todos/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)
  const done = Boolean(body.done)

  const def = DEFAULT_TODOS.find((t) => t.id === id)
  const label = def ? def.label : id

  await admin.from('brand_todos').upsert({
    user_id: me.id,
    todo_id: id,
    label,
    done,
    updated_at: new Date().toISOString(),
  })

  return c.json({ done })
})

// -----------------------------------------------------------------------------
// LISTS (SHORTLISTS)
// -----------------------------------------------------------------------------

// GET /lists
app.get('/lists', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const { data: lists, error } = await admin
    .from('shortlists')
    .select(`
      id,
      name,
      updated_at,
      shortlist_creators (
        creator_id,
        creators (image)
      )
    `)
    .eq('brand_id', me.id)
    .order('updated_at', { ascending: false })

  if (error) throw error

  const result = (lists ?? []).map((l: any) => {
    const sc = l.shortlist_creators ?? []
    const covers = sc.map((item: any) => item.creators?.image).filter(Boolean).slice(0, 4)
    return {
      id: l.id,
      name: l.name,
      count: sc.length,
      updatedAt: l.updated_at,
      covers,
    }
  })

  return c.json(result)
})

// POST /lists
app.post('/lists', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const body = await readJson(c)
  const name = body.name?.trim()

  if (!name) {
    return c.json({ error: { code: 'missing_name', message: 'List name is required' } }, 422)
  }

  const { data: list, error } = await admin
    .from('shortlists')
    .insert({ brand_id: me.id, name })
    .select()
    .single()

  if (error) throw error

  return c.json({
    id: list.id,
    name: list.name,
    count: 0,
    updatedAt: list.updated_at,
    covers: [],
  }, 201)
})

// GET /lists/:id
app.get('/lists/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: list, error } = await admin
    .from('shortlists')
    .select(`
      id,
      name,
      updated_at,
      shortlist_creators (
        creators (*)
      )
    `)
    .eq('id', id)
    .eq('brand_id', me.id)
    .single()

  if (error || !list) {
    return c.json({ error: { code: 'list_not_found', message: 'List not found' } }, 404)
  }

  const creators = (list.shortlist_creators ?? [])
    .map((sc: any) => sc.creators ? formatCreatorCard(sc.creators) : null)
    .filter(Boolean)

  return c.json({
    id: list.id,
    name: list.name,
    count: creators.length,
    updatedAt: list.updated_at,
    creators,
  })
})

// POST /lists/:id/creators
app.post('/lists/:id/creators', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)
  const creatorId = body.creatorId?.trim()

  if (!creatorId) {
    return c.json({ error: { code: 'missing_creator', message: 'creatorId is required' } }, 422)
  }

  // Verify list belongs to brand
  const { data: list, error: listErr } = await admin
    .from('shortlists')
    .select('id')
    .eq('id', id)
    .eq('brand_id', me.id)
    .single()

  if (listErr || !list) {
    return c.json({ error: { code: 'list_not_found', message: 'List not found' } }, 404)
  }

  const { error } = await admin
    .from('shortlist_creators')
    .upsert({ list_id: id, creator_id: creatorId }, { onConflict: 'list_id,creator_id' })

  if (error) throw error

  await admin.from('shortlists').update({ updated_at: new Date().toISOString() }).eq('id', id)

  return c.json({ ok: true, listId: id, creatorId }, 201)
})

// DELETE /lists/:id/creators/:creatorId
app.delete('/lists/:id/creators/:creatorId', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const creatorId = c.req.param('creatorId')

  // Verify list
  const { data: list, error: listErr } = await admin
    .from('shortlists')
    .select('id')
    .eq('id', id)
    .eq('brand_id', me.id)
    .single()

  if (listErr || !list) {
    return c.json({ error: { code: 'list_not_found', message: 'List not found' } }, 404)
  }

  await admin
    .from('shortlist_creators')
    .delete()
    .eq('list_id', id)
    .eq('creator_id', creatorId)

  await admin.from('shortlists').update({ updated_at: new Date().toISOString() }).eq('id', id)

  return new Response(null, { status: 204 })
})

// PATCH /lists/:id
app.patch('/lists/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const body = await readJson(c)
  const name = body.name?.trim()

  if (!name) {
    return c.json({ error: { code: 'missing_name', message: 'List name is required' } }, 422)
  }

  const { data: updated, error } = await admin
    .from('shortlists')
    .update({ name, updated_at: new Date().toISOString() })
    .eq('id', id)
    .eq('brand_id', me.id)
    .select(`
      id,
      name,
      updated_at,
      shortlist_creators (count)
    `)
    .single()

  if (error || !updated) {
    return c.json({ error: { code: 'list_not_found', message: 'List not found' } }, 404)
  }

  return c.json({
    id: updated.id,
    name: updated.name,
    count: updated.shortlist_creators?.[0]?.count ?? 0,
    updatedAt: updated.updated_at,
  })
})

// POST /lists/:id/duplicate
app.post('/lists/:id/duplicate', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: original, error } = await admin
    .from('shortlists')
    .select(`
      id,
      name,
      shortlist_creators (creator_id)
    `)
    .eq('id', id)
    .eq('brand_id', me.id)
    .single()

  if (error || !original) {
    return c.json({ error: { code: 'list_not_found', message: 'List not found' } }, 404)
  }

  const { data: duplicated, error: dupErr } = await admin
    .from('shortlists')
    .insert({
      brand_id: me.id,
      name: `${original.name} (Copy)`,
    })
    .select()
    .single()

  if (dupErr) throw dupErr

  const creatorEntries = (original.shortlist_creators ?? []).map((sc: any) => ({
    list_id: duplicated.id,
    creator_id: sc.creator_id,
  }))

  if (creatorEntries.length > 0) {
    await admin.from('shortlist_creators').insert(creatorEntries)
  }

  return c.json({
    id: duplicated.id,
    name: duplicated.name,
    count: creatorEntries.length,
    updatedAt: duplicated.updated_at,
  }, 201)
})

// DELETE /lists/:id
app.delete('/lists/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { error } = await admin
    .from('shortlists')
    .delete()
    .eq('id', id)
    .eq('brand_id', me.id)

  if (error) throw error
  return new Response(null, { status: 204 })
})

// -----------------------------------------------------------------------------
// DELIVERABLES (CONTENT LIBRARY)
// -----------------------------------------------------------------------------

// GET /deliverables?q=&jobId=&platform=&from=&to=
app.get('/deliverables', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const q = c.req.query('q')?.trim()
  const jobId = c.req.query('jobId')?.trim()
  const platform = c.req.query('platform')?.trim()
  const from = c.req.query('from')
  const to = c.req.query('to')

  let query = admin
    .from('deliverables')
    .select(`
      id,
      content,
      type,
      platform,
      status,
      preview_url,
      download_url,
      delivered_at,
      creators (*),
      campaigns (id, title)
    `)
    .eq('brand_id', me.id)
    .order('delivered_at', { ascending: false })

  if (jobId) query = query.eq('campaign_id', jobId)
  if (platform) query = query.ilike('platform', `%${platform}%`)
  if (from) query = query.gte('delivered_at', from)
  if (to) query = query.lte('delivered_at', to)
  if (q) query = query.ilike('content', `%${q}%`)

  let { data: deliverables, error } = await query
  if (error) throw error

  // If brand has no deliverables yet, seed sample deliverables for demo/test mode
  if (!deliverables || deliverables.length === 0) {
    const seedDeliverables = [
      {
        brand_id: me.id,
        creator_id: 'ananya-rao',
        content: 'Winter Hydration Morning Routine Reel',
        type: 'Reel',
        platform: 'Instagram',
        status: 'Approved',
        preview_url: 'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=600&q=80',
        download_url: 'https://assets.collivra.com/deliverables/ananya_winter_reel.mp4',
        delivered_at: new Date(Date.now() - 86400000 * 2).toISOString(),
      },
      {
        brand_id: me.id,
        creator_id: 'rohan-verma',
        content: 'Unboxing & Sound Test Review',
        type: 'Video',
        platform: 'YouTube',
        status: 'Live',
        preview_url: 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=600&q=80',
        download_url: 'https://assets.collivra.com/deliverables/rohan_sound_review.mp4',
        delivered_at: new Date(Date.now() - 86400000 * 5).toISOString(),
      },
      {
        brand_id: me.id,
        creator_id: 'neha-sharma',
        content: 'Festive Lookbook Outfit Styling',
        type: 'Reel',
        platform: 'Instagram',
        status: 'Needs review',
        preview_url: 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=600&q=80',
        download_url: 'https://assets.collivra.com/deliverables/neha_festive_cut.mp4',
        delivered_at: new Date(Date.now() - 86400000).toISOString(),
      },
    ]

    await admin.from('deliverables').insert(seedDeliverables)

    // Re-fetch with joined relations
    const refetch = await admin
      .from('deliverables')
      .select(`
        id,
        content,
        type,
        platform,
        status,
        preview_url,
        download_url,
        delivered_at,
        creators (*),
        campaigns (id, title)
      `)
      .eq('brand_id', me.id)
      .order('delivered_at', { ascending: false })

    deliverables = refetch.data ?? []
  }

  const results = (deliverables ?? []).map((d: any) => ({
    id: d.id,
    content: d.content,
    type: d.type,
    creator: d.creators ? formatCreatorCard(d.creators) : null,
    job: d.campaigns ? { id: d.campaigns.id, title: d.campaigns.title } : null,
    platform: d.platform,
    deliveredAt: d.delivered_at,
    status: d.status,
    previewUrl: d.preview_url,
    downloadUrl: d.download_url,
  }))

  return c.json(results)
})

// GET /deliverables/export
app.get('/deliverables/export', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const { data: deliverables } = await admin
    .from('deliverables')
    .select(`
      id,
      content,
      type,
      platform,
      status,
      delivered_at,
      preview_url,
      download_url,
      creators (name)
    `)
    .eq('brand_id', me.id)

  const rows = ['ID,Title,Type,Platform,Creator,Status,Delivered At,Download URL']
  for (const d of (deliverables ?? [])) {
    const creatorName = d.creators?.name || 'Creator'
    rows.push(`"${d.id}","${d.content.replace(/"/g, '""')}","${d.type}","${d.platform}","${creatorName}","${d.status}","${d.delivered_at}","${d.download_url}"`)
  }

  return new Response(rows.join('\n'), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': 'attachment; filename="collivra_deliverables.csv"',
    },
  })
})

// GET /deliverables/:id
app.get('/deliverables/:id', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const id = c.req.param('id')
  const { data: d, error } = await admin
    .from('deliverables')
    .select(`
      id,
      content,
      type,
      platform,
      status,
      preview_url,
      download_url,
      delivered_at,
      creators (*),
      campaigns (id, title)
    `)
    .eq('id', id)
    .eq('brand_id', me.id)
    .single()

  if (error || !d) {
    return c.json({ error: { code: 'deliverable_not_found', message: 'Deliverable not found' } }, 404)
  }

  return c.json({
    id: d.id,
    content: d.content,
    type: d.type,
    creator: d.creators ? formatCreatorCard(d.creators) : null,
    job: d.campaigns ? { id: d.campaigns.id, title: d.campaigns.title } : null,
    platform: d.platform,
    deliveredAt: d.delivered_at,
    status: d.status,
    previewUrl: d.preview_url,
    downloadUrl: d.download_url,
  })
})

// -----------------------------------------------------------------------------
// REPORTING & ANALYTICS
// -----------------------------------------------------------------------------

// GET /reporting?period=last_6_months
app.get('/reporting', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const period = c.req.query('period') || 'last_6_months'

  // Fetch top creators for reporting
  const { data: creatorsRaw } = await admin
    .from('creators')
    .select('*')
    .limit(3)

  const topCreators = (creatorsRaw ?? []).map((cr: any, idx: number) => ({
    creator: formatCreatorCard(cr),
    posts: 3 - idx,
    views: 450000 - idx * 110000,
    engagement: `${(5.4 - idx * 0.5).toFixed(1)}%`,
    spend: 32000 - idx * 6000,
    costPer1k: Math.round((32000 - idx * 6000) / ((450000 - idx * 110000) / 1000)),
  }))

  return c.json({
    period,
    stats: [
      { label: 'Total Spend', value: '₹1,45,000', sub: 'Across 6 campaigns' },
      { label: 'Total Views', value: '1.2M', sub: '+24% vs prior period' },
      { label: 'Avg. Engagement Rate', value: '4.8%', sub: 'Industry avg 2.4%' },
      { label: 'Avg. Cost Per 1k Views (CPM)', value: '₹120', sub: 'Best on Instagram Reels' },
    ],
    viewsByMonth: [
      { month: 'May', instagram: 120000, youtube: 60000 },
      { month: 'Jun', instagram: 150000, youtube: 80000 },
      { month: 'Jul', instagram: 180000, youtube: 95000 },
      { month: 'Aug', instagram: 220000, youtube: 110000 },
      { month: 'Sep', instagram: 260000, youtube: 140000 },
      { month: 'Oct', instagram: 310000, youtube: 165000 },
    ],
    spendByPlatform: [
      { label: 'Instagram', amount: 95000, pct: 65 },
      { label: 'YouTube', amount: 50000, pct: 35 },
    ],
    topCreators,
  })
})

// GET /reporting/export?period=
app.get('/reporting/export', async (c) => {
  const me = await requireUser(c)
  if (!me) {
    return c.json({ error: { code: 'unauthorized', message: 'Please sign in' } }, 401)
  }

  const period = c.req.query('period') || 'last_6_months'

  const rows = [
    'Month,Platform,Views,Spend (INR),Engagement',
    'May 2026,Instagram,120000,16000,4.9%',
    'May 2026,YouTube,60000,9000,4.2%',
    'Jun 2026,Instagram,150000,18000,5.1%',
    'Jun 2026,YouTube,80000,11000,4.5%',
    'Jul 2026,Instagram,180000,22000,4.7%',
    'Jul 2026,YouTube,95000,14000,4.6%',
    'Aug 2026,Instagram,220000,26000,5.0%',
    'Aug 2026,YouTube,110000,16000,4.8%',
    'Sep 2026,Instagram,260000,31000,5.2%',
    'Sep 2026,YouTube,140000,20000,4.9%',
    'Oct 2026,Instagram,310000,38000,5.4%',
    'Oct 2026,YouTube,165000,24000,5.0%',
  ]

  return new Response(rows.join('\n'), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="collivra_reporting_${period}.csv"`,
    },
  })
})

// Error format from the spec: { message, code?, fields? }
app.notFound((c) => c.json({ message: 'Not found', code: 'not_found' }, 404))
app.onError((err, c) => {
  console.error(err)
  return c.json({ message: 'Something went wrong', code: 'server_error' }, 500)
})

Deno.serve(app.fetch)

