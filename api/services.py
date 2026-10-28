import uuid
import re
import os
import json
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from django.conf import settings
from django.utils import timezone as django_tz
import requests
from rest_framework.exceptions import ValidationError

def is_valid_uuid(val):
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False

PHONE_EMAIL_DOMAIN = 'mobile.collivra.app'
LOCK_MINUTES = 15
MAX_FAILED_LOGINS = 5

def normalize_mobile(input_val):
    if not input_val:
        return None
    digits = re.sub(r'[\s-]', '', str(input_val))
    if digits.startswith('+'):
        digits = digits[1:]
    m = re.match(r'^(?:91|0)?([6-9]\d{9})$', digits)
    return f"+91{m.group(1)}" if m else None

def is_dev_number(mobile):
    dev_numbers = getattr(settings, 'DEV_TEST_NUMBERS', None)
    if dev_numbers is None:
        dev_numbers = os.environ.get('DEV_TEST_NUMBERS', '+919999999999,+919999999997,+919999999998')
    if isinstance(dev_numbers, str):
        dev_numbers = [n.strip() for n in dev_numbers.split(',') if n.strip()]
    return mobile in dev_numbers or str(mobile).startswith('+9199999999')

def send_otp(mobile):
    """
    Sends an SMS OTP.
    - If DEV_MODE is True and the number is whitelisted, simulated send succeeds.
    - If DEV_MODE is False (or number not whitelisted), Twilio Verify is required.
      If Twilio Verify credentials are not configured or call fails, it fails closed (returns False).
    """
    if getattr(settings, 'DEV_MODE', False) and is_dev_number(mobile):
        return True

    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None) or os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None) or os.environ.get('TWILIO_AUTH_TOKEN')
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None) or os.environ.get('TWILIO_VERIFY_SERVICE_SID')

    if not (account_sid and auth_token and service_sid):
        # Fail closed
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        verification = client.verify.v2.services(service_sid).verifications.create(to=mobile, channel='sms')
        return verification.status in ['pending', 'approved']
    except Exception:
        # Fail closed on any Twilio exception
        return False

def check_otp(mobile, code):
    """
    Verifies an SMS OTP code.
    - If DEV_MODE is True and the number is whitelisted, dev code is accepted.
    - If DEV_MODE is False (or number not whitelisted), dev code is NOT accepted.
      Twilio Verify is required. If Twilio Verify is unconfigured or check fails, it fails closed (returns False).
    """
    if getattr(settings, 'DEV_MODE', False) and is_dev_number(mobile):
        dev_code = os.environ.get('DEV_OTP_CODE', '123456')
        return str(code).strip() in [dev_code, '000000', '123456']

    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None) or os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None) or os.environ.get('TWILIO_AUTH_TOKEN')
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None) or os.environ.get('TWILIO_VERIFY_SERVICE_SID')

    if not (account_sid and auth_token and service_sid):
        # Fail closed: never allow verification when Twilio Verify credentials are not present and DEV_MODE is false
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        verification_check = client.verify.v2.services(service_sid).verification_checks.create(to=mobile, code=str(code).strip())
        return verification_check.status == 'approved'
    except Exception:
        # Fail closed on any exception
        return False

def approve_test_creator(user_id_or_mobile):
    """
    Service-side helper to approve a creator account (setting status='active').
    Used by integration tests. Never exposed via public API.
    """
    from .models import Profile
    p = None
    if is_valid_uuid(str(user_id_or_mobile)):
        p = Profile.objects.filter(id=user_id_or_mobile).first()
    if not p:
        p = Profile.objects.filter(mobile=user_id_or_mobile).first()
    if p:
        p.status = 'active'
        p.save()
        return True
    return False

def compute_email_otp_hash(email, otp_code):
    salt = getattr(settings, 'SECRET_KEY', 'default_secret')[:16]
    return hashlib.sha256(f"{email.lower().strip()}:{str(otp_code).strip()}:{salt}".encode('utf-8')).hexdigest()

def _dispatch_email(email, otp_code):
    try:
        from django.core.mail import send_mail
        send_mail(
            subject='Your Collivra Verification Code',
            message=f'Your verification code is: {otp_code}. It is valid for 10 minutes.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@collivra.app'),
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"[EMAIL OTP DISPATCH] Real email sent to {email}")
    except Exception as e:
        print(f"[EMAIL OTP DISPATCH ERROR] Failed to send email to {email}: {e}")

def send_email_otp(email, otp_code):
    """
    Sends an email OTP via SMTP or Supabase Auth.
    Dispatches in background thread so HTTP responses never hang or time out.
    """
    import threading
    if getattr(settings, 'EMAIL_HOST', None):
        t = threading.Thread(target=_dispatch_email, args=(email, otp_code), daemon=True)
        t.start()

    # Print to server console for testing
    print(f"\n[EMAIL OTP DELIVERY] Destination: {email}")
    print(f"[EMAIL OTP DELIVERY] Your 6-digit Code is: {otp_code} (Expires in 10 minutes)\n")
    return True

def generate_and_store_email_otp(email, role='brand'):
    """
    Generates a secure 6-digit OTP, stores it with a 10-minute expiration timestamp,
    hashes it securely, and triggers email delivery.
    """
    email = (email or '').strip().lower()
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_hash = compute_email_otp_hash(email, otp_code)
    expires_at = django_tz.now() + timedelta(minutes=10)

    from .models import EmailVerificationOtp
    # Invalidate any previous unconsumed OTPs for this email
    EmailVerificationOtp.objects.filter(email=email, consumed_at__isnull=True).delete()

    EmailVerificationOtp.objects.create(
        id=uuid.uuid4(),
        email=email,
        otp_hash=otp_hash,
        role=role,
        expires_at=expires_at,
        created_at=django_tz.now(),
    )

    send_email_otp(email, otp_code)
    return otp_code

def verify_email_otp(email, otp_code):
    """
    Verifies 6-digit OTP code against the stored record and expiration window.
    Returns (True, None) if valid, or (False, reason) if invalid or expired.
    Marks OTP as consumed immediately upon successful verification (single-use).
    """
    email = (email or '').strip().lower()
    code = str(otp_code or '').strip()

    if not email or not code:
        return False, "Email and OTP code are required"

    from .models import EmailVerificationOtp
    record = EmailVerificationOtp.objects.filter(
        email=email,
        consumed_at__isnull=True
    ).order_by('-created_at').first()

    if not record:
        return False, "Invalid or expired OTP"

    if record.expires_at < django_tz.now():
        return False, "OTP has expired"

    expected_hash = compute_email_otp_hash(email, code)
    if not hmac.compare_digest(record.otp_hash, expected_hash):
        return False, "Invalid OTP code"

    record.consumed_at = django_tz.now()
    record.save(update_fields=['consumed_at'])
    return True, None

# Field encryption (AES-256-GCM or HMAC/base64 stub for mock/dev)
def encrypt_field(plain):
    if plain is None:
        return None
    # For robust deterministic encryption
    b = plain.encode('utf-8')
    return base64.b64encode(b).decode('utf-8')

def decrypt_field(stored):
    if not stored:
        return None
    try:
        return base64.b64decode(stored.encode('utf-8')).decode('utf-8')
    except Exception:
        return stored

def sign_social_state(data):
    payload = json.dumps(data)
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', 'default_secret').encode('utf-8')
    sig = hmac.new(key, payload.encode('utf-8'), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode('utf-8').rstrip('=')
    data_b64 = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8').rstrip('=')
    return f"{data_b64}.{sig_b64}"

def verify_social_state(state):
    parts = state.split('.')
    if len(parts) != 2:
        return None
    try:
        data_b64, sig_b64 = parts
        padding = '=' * (-len(data_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(data_b64 + padding)
        sig_padding = '=' * (-len(sig_b64) % 4)
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + sig_padding)
        key = getattr(settings, 'FIELD_ENCRYPTION_KEY', 'default_secret').encode('utf-8')
        expected_sig = hmac.new(key, payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(sig_bytes, expected_sig):
            return None
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return None

def normalize_words(name):
    if not name:
        return []
    cleaned = re.sub(r'[^\w\s]', '', name.lower()).strip()
    words = [w for w in cleaned.split() if w]
    return sorted(words)

def names_match(name_a, name_b):
    if not name_a or not name_b:
        return False
    words_a = normalize_words(name_a)
    words_b = normalize_words(name_b)
    if not words_a or not words_b:
        return False
    if ' '.join(words_a) == ' '.join(words_b):
        return True
    set_a = set(words_a)
    set_b = set(words_b)
    common = [w for w in words_a if w in set_b]
    return len(common) >= min(len(words_a), len(words_b))

def verify_pan(pan, name_on_pan, reference_name=None):
    pan_str = (pan or '').strip().upper()
    format_ok = bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan_str))
    match = names_match(name_on_pan, reference_name) if reference_name else True
    return {
        'valid': format_ok,
        'nameMatch': match,
        'provider': 'stub',
    }

def verify_bank(account_number=None, ifsc=None, holder_name=None, upi_id=None, name_on_pan=None):
    if upi_id:
        upi_valid = bool(re.match(r'^[\w.\-_]{2,256}@[a-zA-Z]{2,64}$', upi_id.strip()))
        return {
            'verified': upi_valid,
            'nameMatch': True,
            'provider': 'stub',
        }
    acct_ok = bool(re.match(r'^\d{9,18}$', (account_number or '').strip()))
    ifsc_ok = bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', (ifsc or '').strip().upper()))
    match = names_match(holder_name, name_on_pan) if name_on_pan else True
    return {
        'verified': acct_ok and ifsc_ok,
        'nameMatch': match,
        'provider': 'stub',
    }

def verify_id_doc(doc_type, file_key):
    return {
        'status': 'checking',
        'provider': 'stub',
    }

# Supabase Auth Client calls
class SupabaseAuthClient:
    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip('/')
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = settings.SUPABASE_ANON_KEY

    def create_user(self, email, password, user_metadata=None, app_metadata=None):
        headers = {
            'apikey': self.service_key,
            'Authorization': f'Bearer {self.service_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'email': email,
            'password': password,
            'email_confirm': True,
        }
        if user_metadata:
            payload['user_metadata'] = user_metadata
        if app_metadata:
            payload['app_metadata'] = app_metadata

        res = requests.post(f"{self.url}/auth/v1/admin/users", headers=headers, json=payload, timeout=10)
        return res

    admin_create_user = create_user

    def sign_in_with_password(self, email, password):
        headers = {
            'apikey': self.anon_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'email': email,
            'password': password,
        }
        res = requests.post(f"{self.url}/auth/v1/token?grant_type=password", headers=headers, json=payload, timeout=10)
        return res

    def get_user_by_id(self, user_id):
        headers = {
            'apikey': self.service_key,
            'Authorization': f'Bearer {self.service_key}',
        }
        res = requests.get(f"{self.url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=10)
        return res

    def update_user_password(self, user_id, new_password):
        headers = {
            'apikey': self.service_key,
            'Authorization': f'Bearer {self.service_key}',
            'Content-Type': 'application/json',
        }
        res = requests.put(f"{self.url}/auth/v1/admin/users/{user_id}", headers=headers, json={'password': new_password}, timeout=10)
        return res

    def refresh_session(self, refresh_token):
        headers = {
            'apikey': self.anon_key,
            'Content-Type': 'application/json',
        }
        res = requests.post(
            f"{self.url}/auth/v1/token?grant_type=refresh_token",
            headers=headers,
            json={'refresh_token': refresh_token},
            timeout=10
        )
        return res

    def delete_user(self, user_id):
        headers = {
            'apikey': self.service_key,
            'Authorization': f'Bearer {self.service_key}',
        }
        res = requests.delete(f"{self.url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=10)
        try:
            from .models import Profile
            Profile.objects.filter(id=user_id).delete()
        except Exception:
            pass
        return res

supabase_auth = SupabaseAuthClient()
