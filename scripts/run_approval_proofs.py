import os
import sys
import uuid
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from django.conf import settings
from django.utils import timezone as django_tz

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection
from api.models import Profile, Creator, VerificationRequest, Campaign, CampaignBid, AuditLog, CreatorProfile, CreatorKyc, SocialAccount
from api.services import supabase_auth

BASE_URL = os.environ.get('COLLIVRA_BASE_URL', 'http://127.0.0.1:8000/api/v1')

def get_account_count():
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.profiles;")
        return cur.fetchone()[0]

def run():
    print("=" * 80)
    print("COLLIVRA APPROVAL FLOW & SECURITY PROOFS")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. INITIAL ACCOUNT COUNT
    initial_count = get_account_count()
    print(f"\n[ACCOUNT AUDIT BEFORE TESTS] Total profiles in database: {initial_count}")

    test_id = str(uuid.uuid4())[:8]
    test_brand_email = f"brand_{test_id}@collivra.test"
    test_creator_email = f"creator_{test_id}@collivra.test"
    test_admin_email = f"test_admin_{test_id}@collivra.test"
    test_pwd = f"TestPass_{test_id}_999"

    created_user_ids = []

    try:
        # =====================================================================
        # 1. BRAND SIGNUP & IMMEDIATE USE
        # =====================================================================
        print("\n--- 1. BRAND SIGNUP (IMMEDIATE ACTIVE STATUS) ---")
        brand_signup_res = requests.post(f"{BASE_URL}/auth/signup", json={
            "name": f"Brand Corp {test_id}",
            "email": test_brand_email,
            "password": test_pwd,
            "companyName": f"Acme {test_id}",
            "role": "brand",
        })
        print(f"Brand Signup Status: {brand_signup_res.status_code}")
        brand_data = brand_signup_res.json()
        brand_token = brand_data.get('token')
        brand_user_id = brand_data.get('user', {}).get('id')
        created_user_ids.append(brand_user_id)

        # Check brand profile status
        brand_prof = Profile.objects.filter(id=brand_user_id).first()
        print(f"Brand Profile Status: {brand_prof.status} (Expected: active)")
        assert brand_prof.status == 'active', f"Expected active, got {brand_prof.status}"

        # Immediate use of brand endpoints (Create campaign)
        camp_res = requests.post(f"{BASE_URL}/campaigns", headers={"Authorization": f"Bearer {brand_token}"}, json={
            "title": f"Spring Launch {test_id}",
            "platform": "Instagram",
            "deliverables": "1 Reel",
            "budgetMin": 1000,
            "budgetMax": 5000,
            "applyBy": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "brief": "Detailed brief for spring launch",
        })
        print(f"Brand Create Campaign -> Status: {camp_res.status_code}")
        assert camp_res.status_code == 201, f"Brand campaign creation failed: {camp_res.text}"
        campaign_id = camp_res.json()['id']

        # =====================================================================
        # 2. CREATOR SIGNUP (UNVERIFIED STATUS & BLOCKED MARKETPLACE)
        # =====================================================================
        print("\n--- 2. CREATOR SIGNUP (UNVERIFIED STATUS & GATED MARKETPLACE) ---")
        creator_signup_res = requests.post(f"{BASE_URL}/auth/signup", json={
            "name": f"Creator User {test_id}",
            "email": test_creator_email,
            "password": test_pwd,
            "role": "creator",
        })
        print(f"Creator Signup Status: {creator_signup_res.status_code}")
        creator_data = creator_signup_res.json()
        creator_token = creator_data.get('token')
        creator_user_id = creator_data.get('user', {}).get('id')
        created_user_ids.append(creator_user_id)

        creator_prof = Profile.objects.filter(id=creator_user_id).first()
        print(f"Creator Profile Status: {creator_prof.status} (Expected: unverified)")
        assert creator_prof.status == 'unverified', f"Expected unverified, got {creator_prof.status}"

        # /auth/me works for creator
        me_res = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {creator_token}"})
        print(f"Creator /auth/me -> Status: {me_res.status_code}, Role: {me_res.json().get('role')}, Status: {me_res.json().get('status')}")
        assert me_res.status_code == 200

        # Creator tries marketplace bid -> MUST return 403 creator_not_approved
        bid_attempt = requests.post(
            f"{BASE_URL}/campaigns/{campaign_id}/bids",
            headers={"Authorization": f"Bearer {creator_token}"},
            json={"price": 2500, "note": "Want to collaborate"}
        )
        print(f"Unapproved Creator Bid -> Status: {bid_attempt.status_code}, Body: {bid_attempt.text}")
        assert bid_attempt.status_code == 403
        assert 'creator_not_approved' in bid_attempt.text, f"Expected creator_not_approved, got {bid_attempt.text}"

        # Creator tries packages -> MUST return 403 creator_not_approved
        pkg_attempt = requests.get(
            f"{BASE_URL}/creators/dummy-id/packages",
            headers={"Authorization": f"Bearer {creator_token}"}
        )
        print(f"Unapproved Creator Packages Access -> Status: {pkg_attempt.status_code}, Body: {pkg_attempt.text}")
        assert pkg_attempt.status_code == 403
        assert 'creator_not_approved' in pkg_attempt.text

        # =====================================================================
        # 3. ONBOARDING SUBMISSION (STATUS PENDING & STILL GATED)
        # =====================================================================
        print("\n--- 3. CREATOR ONBOARDING & SUBMISSION (STATUS PENDING) ---")
        # Profile onboarding
        onb_prof = requests.put(f"{BASE_URL}/creator/onboarding/profile", headers={"Authorization": f"Bearer {creator_token}"}, json={
            "category": "Tech & Gadgets",
            "languages": ["English", "Hindi"],
            "city": "Bengaluru",
            "topics": ["Smartphones", "AI"],
        })
        print(f"Creator Onboarding Profile -> Status: {onb_prof.status_code}")
        assert onb_prof.status_code == 200

        # Submit KYC PAN
        pan_res = requests.post(f"{BASE_URL}/creator/kyc/pan", headers={"Authorization": f"Bearer {creator_token}"}, json={
            "pan": "ABCDE1234F",
            "nameOnPan": f"Creator User {test_id}",
        })
        print(f"Creator KYC PAN -> Status: {pan_res.status_code}")
        assert pan_res.status_code == 200

        # Submit Bank
        bank_res = requests.post(f"{BASE_URL}/creator/bank", headers={"Authorization": f"Bearer {creator_token}"}, json={
            "accountNumber": "123456789012",
            "ifsc": "HDFC0001234",
            "holderName": f"Creator User {test_id}",
        })
        print(f"Creator Bank Details -> Status: {bank_res.status_code}")
        assert bank_res.status_code == 200

        # Submit Onboarding for review
        submit_res = requests.post(f"{BASE_URL}/creator/onboarding/submit", headers={"Authorization": f"Bearer {creator_token}"})
        print(f"Creator Submit Onboarding -> Status: {submit_res.status_code}, Body: {submit_res.text}")
        assert submit_res.status_code == 200

        creator_prof.refresh_from_db()
        print(f"Creator Profile Status after submit: {creator_prof.status} (Expected: pending)")
        assert creator_prof.status == 'pending'

        # Still cannot bid while pending
        bid_pending_attempt = requests.post(
            f"{BASE_URL}/campaigns/{campaign_id}/bids",
            headers={"Authorization": f"Bearer {creator_token}"},
            json={"price": 2500, "note": "Want to collaborate"}
        )
        print(f"Pending Creator Bid -> Status: {bid_pending_attempt.status_code}, Body: {bid_pending_attempt.text}")
        assert bid_pending_attempt.status_code == 403
        assert 'creator_not_approved' in bid_pending_attempt.text

        # =====================================================================
        # 4. ADMIN ENDPOINTS ACCESS CONTROL (BRAND & CREATOR RETURN 403)
        # =====================================================================
        print("\n--- 4. ADMIN ENDPOINT ACCESS CONTROL (BRAND & CREATOR RETURN 403) ---")
        v_req = VerificationRequest.objects.filter(user_id=creator_user_id).first()
        assert v_req is not None, "Verification request was not created"
        v_id = str(v_req.id)

        admin_endpoints = [
            ("GET", f"{BASE_URL}/admin/verifications"),
            ("GET", f"{BASE_URL}/admin/verifications/{v_id}"),
            ("POST", f"{BASE_URL}/admin/verifications/{v_id}/approve", {}),
            ("POST", f"{BASE_URL}/admin/verifications/{v_id}/reject", {"reason": "Test"}),
            ("POST", f"{BASE_URL}/admin/verifications/{v_id}/request-info", {"message": "Test"}),
        ]

        for method, url, *payload in admin_endpoints:
            # Test brand token
            body = payload[0] if payload else None
            res_brand = requests.request(method, url, headers={"Authorization": f"Bearer {brand_token}"}, json=body)
            # Test creator token
            res_creator = requests.request(method, url, headers={"Authorization": f"Bearer {creator_token}"}, json=body)
            print(f"Admin Endpoint [{method} {url.split('/api/v1')[-1]}] -> Brand: {res_brand.status_code}, Creator: {res_creator.status_code}")
            assert res_brand.status_code == 403, f"Brand got {res_brand.status_code} on admin endpoint"
            assert res_creator.status_code == 403, f"Creator got {res_creator.status_code} on admin endpoint"

        # =====================================================================
        # 5. ADMIN ACTIONS: CREATE TEST ADMIN, REQUEST-INFO, REJECT, APPROVE
        # =====================================================================
        print("\n--- 5. ADMIN VERIFICATION WORKFLOW ---")
        # Create test user as brand first, then promote via app_metadata
        admin_signup_res = supabase_auth.create_user(
            email=test_admin_email,
            password=test_pwd,
            user_metadata={"role": "brand", "name": f"Admin {test_id}"}
        )
        assert admin_signup_res.status_code in (200, 201), f"Admin signup failed: {admin_signup_res.text}"
        admin_user_id = admin_signup_res.json()['id']
        created_user_ids.append(admin_user_id)


        # Set role=admin, status=active in public.profiles and auth.users
        with connection.cursor() as cur:
            cur.execute("""
                UPDATE auth.users
                SET raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
                WHERE id = %s;
                UPDATE public.profiles
                SET role = 'admin', status = 'active'
                WHERE id = %s;
            """, [admin_user_id, admin_user_id])

        admin_signin = supabase_auth.sign_in_with_password(test_admin_email, test_pwd)
        assert admin_signin.status_code == 200
        admin_token = admin_signin.json()['access_token']

        # 5a. Admin GET /admin/verifications
        v_list = requests.get(f"{BASE_URL}/admin/verifications?status=pending|needs_info", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"Admin List Verifications -> Status: {v_list.status_code}, Total: {v_list.json().get('total')}")
        assert v_list.status_code == 200

        # 5b. Admin GET /admin/verifications/<id> (Detail, masked PAN/bank, short-lived signed URL, never exposes ciphertext)
        v_detail = requests.get(f"{BASE_URL}/admin/verifications/{v_id}", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"Admin Verification Detail -> Status: {v_detail.status_code}")
        assert v_detail.status_code == 200
        detail_data = v_detail.json()
        assert 'panCiphertext' not in str(detail_data), "Ciphertext exposed in response!"
        assert 'bankAccountCiphertext' not in str(detail_data), "Bank ciphertext exposed in response!"
        print(f"  Masked PAN: {detail_data.get('kyc', {}).get('panMasked')}")
        print(f"  Masked Bank: {detail_data.get('kyc', {}).get('bankAccountMasked')}")

        # 5c. Admin Request Info Path
        req_info_res = requests.post(f"{BASE_URL}/admin/verifications/{v_id}/request-info", headers={"Authorization": f"Bearer {admin_token}"}, json={
            "message": "Please re-upload higher resolution ID document"
        })
        print(f"Admin Request-Info -> Status: {req_info_res.status_code}, Body: {req_info_res.text}")
        assert req_info_res.status_code == 200
        creator_prof.refresh_from_db()
        assert creator_prof.status == 'needs_info'

        # 5d. Admin Reject Path (reason required)
        reject_missing = requests.post(f"{BASE_URL}/admin/verifications/{v_id}/reject", headers={"Authorization": f"Bearer {admin_token}"}, json={})
        print(f"Admin Reject (missing reason) -> Status: {reject_missing.status_code}")
        assert reject_missing.status_code == 422

        reject_res = requests.post(f"{BASE_URL}/admin/verifications/{v_id}/reject", headers={"Authorization": f"Bearer {admin_token}"}, json={
            "reason": "PAN name does not match government identity record"
        })
        print(f"Admin Reject -> Status: {reject_res.status_code}, Body: {reject_res.text}")
        assert reject_res.status_code == 200
        creator_prof.refresh_from_db()
        assert creator_prof.status == 'needs_info', "Status must stay needs_info so creator can fix"

        # Creator resubmits
        resubmit_res = requests.post(f"{BASE_URL}/creator/onboarding/submit", headers={"Authorization": f"Bearer {creator_token}"})
        assert resubmit_res.status_code == 200
        creator_prof.refresh_from_db()
        assert creator_prof.status == 'pending'

        # 5e. Admin Approve Path
        approve_res = requests.post(f"{BASE_URL}/admin/verifications/{v_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"Admin Approve -> Status: {approve_res.status_code}, Body: {approve_res.text}")
        assert approve_res.status_code == 200
        creator_prof.refresh_from_db()
        assert creator_prof.status == 'active'

        # Check listed creator row was created and active
        creator_row = Creator.objects.filter(id=str(creator_user_id)).first()
        assert creator_row is not None and creator_row.status == 'active' and creator_row.is_seed is False
        print(f"  Verified Creator row created in catalog: ID={creator_row.id}, Status={creator_row.status}, is_seed={creator_row.is_seed}")

        # Check audit log written
        audit_entry = AuditLog.objects.filter(entity_id=v_id, action='verification_approved').first()
        assert audit_entry is not None, "Audit log entry not written!"
        print(f"  Audit log verified: Action={audit_entry.action}, Actor={audit_entry.actor_id}")

        # 5f. Approve twice is idempotent
        approve_twice = requests.post(f"{BASE_URL}/admin/verifications/{v_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"Admin Approve Twice -> Status: {approve_twice.status_code}, Body: {approve_twice.text}")
        assert approve_twice.status_code == 200

        # 5g. Creator can now bid successfully!
        bid_success = requests.post(
            f"{BASE_URL}/campaigns/{campaign_id}/bids",
            headers={"Authorization": f"Bearer {creator_token}"},
            json={"price": 2500, "note": "Now active and ready to deliver!"}
        )
        print(f"Approved Creator Bid -> Status: {bid_success.status_code}, Body: {bid_success.text}")
        assert bid_success.status_code == 201

        # =====================================================================
        # 6. SUSPENDED CREATOR BLOCKED ON NEXT REQUEST
        # =====================================================================
        print("\n--- 6. SUSPENDED ACCOUNT BLOCK ON NEXT REQUEST ---")
        creator_prof.status = 'suspended'
        creator_prof.save()

        # Immediate next request from creator token -> 403
        blocked_res = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {creator_token}"})
        print(f"Suspended Creator /auth/me -> Status: {blocked_res.status_code}, Body: {blocked_res.text}")
        assert blocked_res.status_code == 403

        # Restore status for subsequent tests
        creator_prof.status = 'active'
        creator_prof.save()

        # =====================================================================
        # 7. PREVENT MASS ASSIGNMENT (ROLE / STATUS IN BODY & UPDATEUSER)
        # =====================================================================
        print("\n--- 7. MASS ASSIGNMENT & METADATA TAMPERING PREVENTION ---")
        # 7a. PATCH /auth/me with role or status -> 422
        patch_res = requests.patch(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {brand_token}"},
            json={"status": "active", "role": "admin"}
        )
        print(f"PATCH /auth/me with role/status -> Status: {patch_res.status_code}, Body: {patch_res.text}")
        assert patch_res.status_code == 422

        # 7b. Direct Supabase Auth updateUser changing user_metadata does not change profile
        update_meta_res = requests.put(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {brand_token}",
                "Content-Type": "application/json",
            },
            json={"data": {"role": "admin", "status": "active"}}
        )
        print(f"Direct Supabase updateUser -> Status: {update_meta_res.status_code}")
        brand_prof.refresh_from_db()
        print(f"Profile role after updateUser: {brand_prof.role} (Expected: brand)")
        assert brand_prof.role == 'brand', "Profile role was illegally modified by user_metadata!"

        print("\nALL 7 SUITES OF APPROVAL & SECURITY PROOFS PASSED SUCCESSFULLY!")

    finally:
        # =====================================================================
        # 8. ACCOUNT CLEANUP & VERIFICATION OF ZERO ACCOUNTS LEFT BEHIND
        # =====================================================================
        print("\n--- CLEANUP OF TEST ACCOUNTS ---")
        with connection.cursor() as cur:
            for u_id in created_user_ids:
                if u_id:
                    cur.execute("DELETE FROM public.audit_log WHERE actor_id = %s OR entity_id = %s;", [u_id, u_id])
                    cur.execute("DELETE FROM public.campaign_bids WHERE creator_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.campaigns WHERE brand_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.creators WHERE id = %s;", [str(u_id)])
                    cur.execute("DELETE FROM public.verification_requests WHERE user_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.creator_profiles WHERE user_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.creator_kyc WHERE user_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.social_accounts WHERE user_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.brand_profiles WHERE user_id = %s;", [u_id])
                    cur.execute("DELETE FROM public.profiles WHERE id = %s;", [u_id])
                    cur.execute("DELETE FROM auth.users WHERE id = %s;", [u_id])
                    print(f"Deleted test account: {u_id}")

        final_count = get_account_count()
        print(f"\n[ACCOUNT AUDIT AFTER TESTS]")
        print(f"  Count Before: {initial_count}")
        print(f"  Count After:  {final_count}")
        print(f"  Difference:   {final_count - initial_count} (Must be exactly 0)")
        assert final_count == initial_count, f"Account leak detected! Before: {initial_count}, After: {final_count}"
        print("  VERIFIED: Zero test accounts left behind!")

if __name__ == '__main__':
    run()
