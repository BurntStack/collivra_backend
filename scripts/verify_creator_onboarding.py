import os
import sys
import uuid
from datetime import date, timedelta
import django

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone as django_tz
from rest_framework.test import APIClient
from api.models import Profile, CreatorProfiles, AuditLog
from api.authentication import SupabaseUser
from api.services import supabase_auth


def run_tests():
    print("=" * 65)
    print("STARTING CREATOR ONBOARDING & ADMIN VERIFICATION QUEUE TESTS")
    print("=" * 65)

    client = APIClient()

    # 1. Test unauthenticated request
    print("\n--- 1. Testing Unauthenticated Request ---")
    res = client.get('/api/v1/creator/onboarding')
    print("Unauth GET status:", res.status_code)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"

    res = client.post('/api/v1/creator/onboarding', {'city': 'Mumbai'}, format='json')
    print("Unauth POST status:", res.status_code)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print(" Unauthenticated requests correctly rejected (401).")

    # 2. Setup real test creator user
    test_id = uuid.uuid4().hex[:6]
    creator_email = f"creator_onboarding_{test_id}@collivra.test"
    test_password = "SecurePassword123!"

    signup_res = supabase_auth.create_user(
        email=creator_email,
        password=test_password,
        user_metadata={"role": "creator", "name": f"Pending Creator {test_id}"}
    )
    assert signup_res.status_code in (200, 201), f"Creator signup failed: {signup_res.text}"
    creator_user_id = signup_res.json()['id']

    creator_profile = Profile.objects.filter(id=creator_user_id).first()
    assert creator_profile is not None, "Profile was not created by trigger"
    creator_profile.is_profile_completed = False
    creator_profile.approval_status = 'pending'
    creator_profile.save()
    print(f"\nCreated initial creator user (id: {creator_user_id}, email: {creator_email})")

    creator_auth_user = SupabaseUser(
        user_id=creator_user_id,
        email=creator_email,
        role='creator',
        status='unverified',
        raw_claims={'sub': str(creator_user_id), 'email': creator_email}
    )
    client.force_authenticate(user=creator_auth_user)

    # 3. Test Underage (Age < 18) rejection
    print("\n--- 2. Testing Strict 18+ Age Validation ---")
    # 16-year-old DOB
    underage_dob = (date.today() - timedelta(days=16 * 365.25)).strftime('%Y-%m-%d')
    underage_payload = {
        'firstName': 'Minor',
        'lastName': 'Creator',
        'dateOfBirth': underage_dob,
        'city': 'Mumbai',
        'regionState': 'Maharashtra',
        'gender': 'Male',
    }
    res = client.post('/api/v1/creator/onboarding', underage_payload, format='json')
    print(f"Underage submission (DOB: {underage_dob}) status:", res.status_code)
    assert res.status_code == 422, f"Expected 422 for underage, got {res.status_code}"
    dob_errors = str(res.json().get('errors', {}).get('dob', ''))
    assert '18 years old' in dob_errors, f"Expected 18+ error message, got {dob_errors}"
    print(" Underage applicant strictly rejected:", dob_errors)

    # Future date check
    future_dob = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
    res_future = client.post('/api/v1/creator/onboarding', {'dateOfBirth': future_dob, 'city': 'Delhi', 'regionState': 'Delhi'}, format='json')
    assert res_future.status_code == 422
    print(" Future date strictly rejected (422).")

    # 4. Test Invalid PAN Format
    print("\n--- 3. Testing Field Validation (PAN & Missing Fields) ---")
    bad_pan_payload = {
        'dateOfBirth': '2000-01-01',
        'city': 'Mumbai',
        'regionState': 'Maharashtra',
        'panNumber': 'INVALID123',  # Bad format
    }
    res_pan = client.post('/api/v1/creator/onboarding', bad_pan_payload, format='json')
    assert res_pan.status_code == 422
    assert 'pan_number' in res_pan.json().get('errors', {})
    print(" Invalid PAN format correctly rejected (422).")

    # 5. Successful Creator Onboarding Submission (Age >= 18)
    print("\n--- 4. Testing Valid Creator Onboarding Submission ---")
    valid_payload = {
        'firstName': 'Ananya',
        'lastName': 'Verma',
        'dateOfBirth': '2001-05-20',
        'gender': 'Female',
        'category': 'Fashion & Styling',
        'bio': 'Sustainable fashion enthusiast sharing weekly styling tips and lookbooks.',
        'languages': ['English', 'Hindi'],
        'city': 'Bengaluru',
        'regionState': 'Karnataka',
        'country': 'India',
        'instagramHandle': '@ananya_looks',
        'youtubeHandle': 'ananyalooks',
        'panNumber': 'ABCDE1234F',
    }
    res_submit = client.post('/api/v1/creator/onboarding', valid_payload, format='json')
    print("Valid creator submission status:", res_submit.status_code)
    print("Response payload:", res_submit.json())
    assert res_submit.status_code == 200, f"Expected 200, got {res_submit.status_code}"

    # Verify DB state
    creator_profile.refresh_from_db()
    assert creator_profile.is_profile_completed is True, "Profile is_profile_completed must be True"
    assert creator_profile.role == 'creator', "Profile role must be 'creator'"
    assert creator_profile.status == 'active', "Profile status must be 'active'"
    assert creator_profile.approval_status == 'approved', "Profile approval_status must be 'approved'"
    assert creator_profile.name == 'Ananya Verma'

    cp = CreatorProfiles.objects.filter(user=creator_profile).first()
    assert cp is not None, "CreatorProfiles record must exist"
    assert cp.approval_status == 'approved', "CreatorProfile approval_status must be 'approved'"
    assert cp.kyc_status == 'verified', "kyc_status should be 'verified'"
    assert cp.instagram_handle == 'ananya_looks', "Instagram handle should be stripped of leading @"
    assert cp.dob == date(2001, 5, 20)
    assert cp.pan_number == 'ABCDE1234F'
    print(" Database state verified: is_profile_completed=True, status='active', approval_status='approved'.")

    # 6. Test GET Creator Onboarding
    print("\n--- 5. Testing GET Creator Onboarding ---")
    res_get = client.get('/api/v1/creator/onboarding')
    assert res_get.status_code == 200
    assert res_get.json().get('creatorProfile', {}).get('instagramHandle') == 'ananya_looks'
    print(" GET endpoint returned saved creator details.")

    # 7. Superadmin Verification Queue Access
    print("\n--- 6. Testing Superadmin Verification Queue ---")
    # Non-admin should be rejected (403)
    res_forbidden = client.get('/api/v1/admin/creators/queue')
    print("Non-admin queue access status:", res_forbidden.status_code)
    assert res_forbidden.status_code == 403, f"Expected 403 for non-admin, got {res_forbidden.status_code}"

    from django.db import connection

    # Authenticate as superadmin via Supabase Auth
    admin_test_id = uuid.uuid4().hex[:6]
    admin_email = f"test_admin_{admin_test_id}@collivra.test"
    admin_res = supabase_auth.create_user(
        email=admin_email,
        password="SecureAdmin123!",
        user_metadata={"role": "brand", "name": f"Admin {admin_test_id}"}
    )
    assert admin_res.status_code in (200, 201), f"Admin user creation failed: {admin_res.text}"
    admin_id = admin_res.json()['id']

    with connection.cursor() as cur:
        cur.execute("""
            UPDATE auth.users
            SET raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
            WHERE id = %s;
            UPDATE public.profiles
            SET role = 'admin', status = 'active', email = %s
            WHERE id = %s;
        """, [admin_id, admin_email, admin_id])

    admin_profile = Profile.objects.filter(id=admin_id).first()
    assert admin_profile is not None
    assert admin_profile.role == 'admin'

    admin_user = SupabaseUser(
        user_id=admin_id,
        email=admin_email,
        role='admin',
        status='active',
        raw_claims={'sub': str(admin_id), 'email': admin_email}
    )
    client.force_authenticate(user=admin_user)

    # For queue endpoint testing, set one profile to pending
    CreatorProfiles.objects.filter(user=creator_profile).update(approval_status='pending')
    creator_profile.approval_status = 'pending'
    creator_profile.save()

    # Superadmin GET queue
    res_queue = client.get('/api/v1/admin/creators/queue?status=pending')
    print("Superadmin queue status:", res_queue.status_code)
    assert res_queue.status_code == 200
    queue_data = res_queue.json()
    print(f"Total creators in pending queue: {queue_data.get('total')}")
    found = any(item.get('userId') == str(creator_user_id) for item in queue_data.get('items', []))
    assert found, "Submitted creator must appear in superadmin pending verification queue"
    print(" Creator successfully found in pending verification queue!")

    # 8. Superadmin Approval Action
    print("\n--- 7. Testing Superadmin Approval Action ---")
    res_approve = client.post(f'/api/v1/admin/creators/{creator_user_id}/approve')
    print("Approve status:", res_approve.status_code)
    assert res_approve.status_code == 200
    print("Approve response:", res_approve.json().get('message'))

    # Verify approved state in DB
    creator_profile.refresh_from_db()
    cp.refresh_from_db()
    assert creator_profile.approval_status == 'approved'
    assert creator_profile.status == 'active'
    assert cp.approval_status == 'approved'
    assert cp.kyc_status == 'verified'

    # Verify audit log
    audit_entry = AuditLog.objects.filter(entity_id=str(creator_user_id), action='creator_approved').first()
    assert audit_entry is not None, "AuditLog entry for approval must be created"
    print(" Creator profile approved: user status='active', approval_status='approved', AuditLog logged.")

    # 9. Superadmin Rejection Action
    print("\n--- 8. Testing Superadmin Rejection Action ---")
    res_reject = client.post(
        f'/api/v1/admin/creators/{creator_user_id}/reject',
        {'reason': 'Incomplete portfolio documentation'},
        format='json'
    )
    print("Reject status:", res_reject.status_code)
    assert res_reject.status_code == 200
    creator_profile.refresh_from_db()
    cp.refresh_from_db()
    assert creator_profile.approval_status == 'rejected'
    assert cp.approval_status == 'rejected'
    assert AuditLog.objects.filter(entity_id=str(creator_user_id), action='creator_rejected').exists()
    print(" Creator profile rejected and audit log created.")

    # Clean up test accounts
    print("\n--- 9. Cleaning Up Test Data ---")
    AuditLog.objects.filter(entity_id=str(creator_user_id)).delete()
    CreatorProfiles.objects.filter(user=creator_profile).delete()
    supabase_auth.delete_user(str(creator_user_id))
    supabase_auth.delete_user(str(admin_id))
    print(" Cleanup complete.")
    print("\n ALL CREATOR ONBOARDING & SUPERADMIN QUEUE TESTS PASSED 100% PERFECTLY!")


if __name__ == '__main__':
    run_tests()
