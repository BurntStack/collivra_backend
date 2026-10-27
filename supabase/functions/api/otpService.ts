export function normalizeMobile(input: string): string | null {
  const digits = input.replace(/[\s-]/g, '').replace(/^\+/, '')
  const m = digits.match(/^(?:91|0)?([6-9]\d{9})$/)
  return m ? `+91${m[1]}` : null
}

// Dev bypass works only when DEV_MODE=true AND the number is on the test list.
function isDevNumber(mobile: string): boolean {
  if (Deno.env.get('DEV_MODE') !== 'true') return false
  const list = (Deno.env.get('DEV_TEST_NUMBERS') ?? '')
    .split(',').map((s) => s.trim()).filter(Boolean)
  return list.includes(mobile)
}

async function twilio(path: string, form: Record<string, string>): Promise<Response> {
  const sid = Deno.env.get('TWILIO_ACCOUNT_SID')
  const token = Deno.env.get('TWILIO_AUTH_TOKEN')
  const service = Deno.env.get('TWILIO_VERIFY_SERVICE_SID')
  if (!sid || !token || !service) throw new Error('Twilio secrets are not configured')
  return await fetch(`https://verify.twilio.com/v2/Services/${service}/${path}`, {
    method: 'POST',
    headers: {
      Authorization: 'Basic ' + btoa(`${sid}:${token}`),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams(form),
  })
}

export async function sendOtp(mobile: string): Promise<void> {
  if (isDevNumber(mobile)) return
  const res = await twilio('Verifications', { To: mobile, Channel: 'sms' })
  if (!res.ok) throw new Error(`Twilio send failed: ${res.status} ${await res.text()}`)
}

export async function checkOtp(mobile: string, code: string): Promise<boolean> {
  if (isDevNumber(mobile)) return code === (Deno.env.get('DEV_OTP_CODE') ?? '123456')
  const res = await twilio('VerificationCheck', { To: mobile, Code: code })
  if (!res.ok) return false // 404 = expired, used, or too many attempts
  const data = await res.json()
  return data.status === 'approved'
}
