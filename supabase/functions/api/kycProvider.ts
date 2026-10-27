// KYC verification provider abstraction (stub vs production provider)

function normalizeWords(name: string): string[] {
  return name
    .toLowerCase()
    .replace(/[^\w\s]/g, '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .sort()
}

export function namesMatch(nameA?: string | null, nameB?: string | null): boolean {
  if (!nameA || !nameB) return false
  const wordsA = normalizeWords(nameA)
  const wordsB = normalizeWords(nameB)
  if (!wordsA.length || !wordsB.length) return false
  // Exact match or permutation of words match
  if (wordsA.join(' ') === wordsB.join(' ')) return true
  // Subset match (e.g. initial or middle name missing)
  const setA = new Set(wordsA)
  const setB = new Set(wordsB)
  const common = wordsA.filter((w) => setB.has(w))
  return common.length >= Math.min(wordsA.length, wordsB.length);
}

export interface PanVerificationResult {
  valid: boolean
  nameMatch: boolean
  provider: 'stub' | 'live'
}

export async function verifyPan(
  pan: string,
  nameOnPan: string,
  referenceName?: string | null
): Promise<PanVerificationResult> {
  const mode = Deno.env.get('KYC_MODE') ?? 'stub'
  if (mode === 'stub') {
    const formatOk = /^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)
    const match = referenceName ? namesMatch(nameOnPan, referenceName) : true
    return {
      valid: formatOk,
      nameMatch: match,
      provider: 'stub',
    }
  }
  throw new Error(`Unsupported KYC_MODE: ${mode}`)
}

export interface BankVerificationResult {
  verified: boolean
  nameMatch: boolean
  provider: 'stub' | 'live'
}

export async function verifyBank(
  input: {
    accountNumber?: string
    ifsc?: string
    holderName?: string
    upiId?: string
  },
  nameOnPan?: string | null
): Promise<BankVerificationResult> {
  const mode = Deno.env.get('KYC_MODE') ?? 'stub'
  if (mode === 'stub') {
    if (input.upiId) {
      const upiValid = /^[\w.\-_]{2,256}@[a-zA-Z]{2,64}$/.test(input.upiId)
      return {
        verified: upiValid,
        nameMatch: true,
        provider: 'stub',
      }
    }
    const acctOk = /^\d{9,18}$/.test(input.accountNumber ?? '')
    const ifscOk = /^[A-Z]{4}0[A-Z0-9]{6}$/.test(input.ifsc ?? '')
    const match = namesMatch(input.holderName, nameOnPan)
    return {
      verified: acctOk && ifscOk,
      nameMatch: match,
      provider: 'stub',
    }
  }
  throw new Error(`Unsupported KYC_MODE: ${mode}`)
}

export interface IdVerificationResult {
  status: 'checking' | 'verified' | 'failed'
  provider: 'stub' | 'live'
}

export async function verifyId(
  _docType: string,
  _fileKey: string
): Promise<IdVerificationResult> {
  const mode = Deno.env.get('KYC_MODE') ?? 'stub'
  if (mode === 'stub') {
    return {
      status: 'checking',
      provider: 'stub',
    }
  }
  throw new Error(`Unsupported KYC_MODE: ${mode}`)
}
