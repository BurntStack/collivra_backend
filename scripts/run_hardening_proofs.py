import os
import sys
import json
import uuid
import time
import threading
import requests
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone as django_tz
from api.models import Profile, Creator, Campaign, CampaignBid, Order, OrderMessage, Shortlist
from api.services import SupabaseAuthClient, approve_test_creator, send_otp, check_otp

LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_results.log'))
BASE_URL = 'http://127.0.0.1:8000'

def log(msg):
    print(msg)
    with open(LOG_FILE, 'a') as f:
        f.write(msg + '\n')

log("=" * 80)
log(f"COLLIVRA HARDENING PROOFS - {datetime.now().isoformat()}")
log("=" * 80)

auth_client = SupabaseAuthClient()
created_user_ids = []

def cleanup():
    log("\n--- CLEANUP OF TEST ACCOUNTS & ROWS ---")
    for uid in created_user_ids:
        try:
            Creator.objects.filter(id=str(uid)).delete()
            auth_client.delete_user(uid)
            log(f"Deleted test user & creator row: {uid}")
        except Exception as e:
            log(f"Cleanup error for {uid}: {e}")

try:
    # -------------------------------------------------------------
    # 1. SETUP TEST USERS (Brand and Creator)
    # -------------------------------------------------------------
    rand_suffix = str(int(time.time()))[-6:]
    brand_email = f"proof_brand_{rand_suffix}@collivra.test"
    brand_pass = "TestPass123!Safe"
    
    res = auth_client.create_user(brand_email, brand_pass, {'role': 'brand', 'name': 'Proof Brand'})
    brand_user = res.json()
    brand_uid = brand_user['id']
    created_user_ids.append(brand_uid)
    Profile.objects.update_or_create(
        id=brand_uid,
        defaults={'email': brand_email, 'role': 'brand', 'name': 'Proof Brand', 'status': 'active', 'is_verified': True}
    )
    login_res = auth_client.sign_in_with_password(brand_email, brand_pass)
    brand_token = login_res.json()['access_token']
    brand_headers = {'Authorization': f'Bearer {brand_token}', 'Content-Type': 'application/json'}
    log(f"[SETUP] Created & authenticated Brand: {brand_email} ({brand_uid})")

    creator_mobile = f"+9198888{rand_suffix[:5]}"
    creator_email = f"creator_{rand_suffix}@collivra.test"
    creator_pass = "TestPass123!Creator"
    res = auth_client.create_user(creator_email, creator_pass, {'role': 'creator', 'name': 'Proof Creator', 'mobile': creator_mobile})
    creator_user = res.json()
    creator_uid = creator_user['id']
    created_user_ids.append(creator_uid)
    Profile.objects.update_or_create(
        id=creator_uid,
        defaults={'email': creator_email, 'role': 'creator', 'name': 'Proof Creator', 'mobile': creator_mobile, 'status': 'unverified', 'is_verified': False}
    )
    login_res = auth_client.sign_in_with_password(creator_email, creator_pass)
    creator_token = login_res.json()['access_token']
    creator_headers = {'Authorization': f'Bearer {creator_token}', 'Content-Type': 'application/json'}
    log(f"[SETUP] Created & authenticated Creator: {creator_email} ({creator_uid})")

    # -------------------------------------------------------------
    # REQUIREMENT 1: BIDS ENFORCEMENTS & PROOFS
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 1: POST /campaigns/<pk>/bids ENFORCEMENTS")
    log("=" * 50)

    # Create active campaign
    camp_open = Campaign.objects.create(
        id=uuid.uuid4(),
        brand=Profile.objects.get(id=brand_uid),
        title='Open Campaign for Proofs',
        status='open_for_bids',
        platform='Instagram',
        deliverables='1 Reel',
        budget_min=1000,
        budget_max=5000,
        apply_by=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        created_at=django_tz.now(),
        updated_at=django_tz.now(),
    )
    # Create closed campaign
    camp_closed = Campaign.objects.create(
        id=uuid.uuid4(),
        brand=Profile.objects.get(id=brand_uid),
        title='Closed Campaign',
        status='closed',
        platform='Instagram',
        budget_min=1000,
        budget_max=5000,
        apply_by=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        created_at=django_tz.now(),
        updated_at=django_tz.now(),
    )
    # Create expired applyBy campaign
    camp_expired = Campaign.objects.create(
        id=uuid.uuid4(),
        brand=Profile.objects.get(id=brand_uid),
        title='Expired Campaign',
        status='open_for_bids',
        platform='Instagram',
        budget_min=1000,
        budget_max=5000,
        apply_by=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        created_at=django_tz.now(),
        updated_at=django_tz.now(),
    )

    # Create campaign with unparseable applyBy deadline
    camp_unparseable = Campaign.objects.create(
        id=uuid.uuid4(),
        brand=Profile.objects.get(id=brand_uid),
        title='Unparseable Deadline Campaign',
        status='open_for_bids',
        platform='Instagram',
        budget_min=1000,
        budget_max=5000,
        apply_by='invalid-deadline-string',
        created_at=django_tz.now(),
        updated_at=django_tz.now(),
    )

    # 1a. Inactive Creator Check (profile status = unverified)
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 2500})
    log(f"1a. Inactive Creator Bid -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    # Service-side helper approval of user profile
    approve_test_creator(creator_uid)
    log(f"[SERVICE HELPER] Approved user profile {creator_uid} to 'active' status")

    # 1b. Unlisted Creator Check (User profile active, but NOT listed in Creator catalog)
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 2500})
    log(f"1b. Unlisted Creator Bid -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"
    assert r.json().get('error', {}).get('code') == 'creator_not_listed'

    # 1c. Explicitly prepare test Creator catalog row
    test_creator = Creator.objects.create(
        id=str(creator_uid),
        name='Proof Creator',
        category='Lifestyle',
        location='India',
        city='Bengaluru',
        followers='10k',
        follower_count=10000,
        platform='Instagram',
        rating=5.0,
        review_count=0,
        price_from=2500,
        deliverable='1 Post',
        image='https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80',
        top_creator=False,
        replies_within='24 hours',
        is_seed=False,
        status='active',
        created_at=django_tz.now(),
        updated_at=django_tz.now(),
    )
    log(f"[EXPLICIT PREPARATION] Created verified Creator catalog row for {creator_uid}")

    # 2. Closed Campaign Check
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_closed.id}/bids", headers=creator_headers, json={'price': 2500})
    log(f"2. Closed Campaign Bid -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 409, f"Expected 409, got {r.status_code}"

    # 3a. Expired applyBy Check
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_expired.id}/bids", headers=creator_headers, json={'price': 2500})
    log(f"3a. Expired Deadline Bid -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 409, f"Expected 409, got {r.status_code}"

    # 3b. Unparseable applyBy Check (fail closed)
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_unparseable.id}/bids", headers=creator_headers, json={'price': 2500})
    log(f"3b. Unparseable Deadline Bid -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 409, f"Expected 409, got {r.status_code}"

    # 4. Price Below budget_min Check
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 500})
    log(f"4. Price < budget_min (500 < 1000) -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    # 5. Price Above budget_max Check
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 6000})
    log(f"5. Price > budget_max (6000 > 5000) -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    # 6. Price Non-integer or < 1 Check
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 0})
    log(f"6a. Price < 1 (0) -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': "not_an_int"})
    log(f"6b. Price non-integer ('not_an_int') -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    # 7. Valid Bid Check
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 2500, 'note': 'High quality reel'})
    log(f"7. Valid Bid (price: 2500) -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 201, f"Expected 201, got {r.status_code}"
    bid_id = r.json()['id']

    # 8. Duplicate Bid Check (Unique constraint)
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids", headers=creator_headers, json={'price': 3000})
    log(f"8. Duplicate Bid by same creator -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 409, f"Expected 409, got {r.status_code}"

    # -------------------------------------------------------------
    # REQUIREMENT 2: SEED DATA HIDING PROOFS
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 2: SEED DATA HIDING PROOFS (SHOW_SEED_DATA = False)")
    log("=" * 50)

    seed_creator_id = 'vikram-malhotra'
    
    # 1. Detail
    r = requests.get(f"{BASE_URL}/api/v1/creators/{seed_creator_id}", headers=brand_headers)
    log(f"Seed Creator Detail ({seed_creator_id}) -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 2. Packages
    r = requests.get(f"{BASE_URL}/api/v1/creators/{seed_creator_id}/packages", headers=brand_headers)
    log(f"Seed Creator Packages -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 3. Reviews
    r = requests.get(f"{BASE_URL}/api/v1/creators/{seed_creator_id}/reviews", headers=brand_headers)
    log(f"Seed Creator Reviews -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 4. Similar
    r = requests.get(f"{BASE_URL}/api/v1/creators/{seed_creator_id}/similar", headers=brand_headers)
    log(f"Seed Creator Similar -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 5. Save
    r = requests.post(f"{BASE_URL}/api/v1/creators/{seed_creator_id}/save", headers=brand_headers)
    log(f"Seed Creator Save -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 6. Cart items
    r = requests.post(f"{BASE_URL}/api/v1/cart/items", headers=brand_headers, json={'creatorId': seed_creator_id, 'packageId': 'pkg-1', 'quantity': 1})
    log(f"Seed Creator Cart Add -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 7. Offers
    r = requests.post(f"{BASE_URL}/api/v1/offers", headers=brand_headers, json={'creatorId': seed_creator_id, 'deliverable': 'Custom Video', 'budget': 5000})
    log(f"Seed Creator Custom Offer -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 8. Orders
    r = requests.post(f"{BASE_URL}/api/v1/orders", headers=brand_headers, json={'creatorId': seed_creator_id, 'amount': 5000, 'deliverable': 'Custom Video'})
    log(f"Seed Creator Order Create -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    now = django_tz.now()
    sl = Shortlist.objects.create(id=uuid.uuid4(), brand=Profile.objects.get(id=brand_uid), name='Test List', created_at=now, updated_at=now)
    r = requests.post(f"{BASE_URL}/api/v1/lists/{sl.id}/creators", headers=brand_headers, json={'creatorId': seed_creator_id})
    log(f"Seed Creator Shortlist Add -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 404

    # 10. Creator Listing
    r = requests.get(f"{BASE_URL}/api/v1/creators")
    creators_list = r.json().get('results', [])
    seed_names = ['Vikram Malhotra', 'Priya Iyer', 'Kabir Mehta', 'Sneha Kapoor']
    found_seeds = [c['name'] for c in creators_list if c['name'] in seed_names]
    log(f"Creator Listing -> Total: {len(creators_list)}, Found Seed Names: {found_seeds}")
    assert len(found_seeds) == 0, f"Seed creators returned in listing: {found_seeds}"

    # -------------------------------------------------------------
    # REQUIREMENT 4: THROTTLING PROOFS & SEPARATE IP BUCKETS
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 4: THROTTLING PROOFS (LoginRateThrottle 5/min & X-Forwarded-For)")
    log("=" * 50)

    # Bucket A (IP 198.51.100.10)
    ip_a_headers = {'X-Forwarded-For': '198.51.100.10'}
    throttled_a = False
    for i in range(1, 8):
        r = requests.post(f"{BASE_URL}/api/v1/auth/login", headers=ip_a_headers, json={'email': 'wrong@test.com', 'password': 'wrong'})
        log(f"IP A (198.51.100.10) login attempt {i} -> Status: {r.status_code}")
        if r.status_code == 429:
            throttled_a = True
            log(f"IP A reached rate limit on attempt {i} (Status: 429): {r.text}")
            break
    assert throttled_a, "IP A was not throttled"

    # Bucket B (IP 198.51.100.20) - Should NOT be throttled because it has a separate bucket!
    ip_b_headers = {'X-Forwarded-For': '198.51.100.20'}
    r_b = requests.post(f"{BASE_URL}/api/v1/auth/login", headers=ip_b_headers, json={'email': 'wrong@test.com', 'password': 'wrong'})
    log(f"IP B (198.51.100.20) initial login attempt -> Status: {r_b.status_code}")
    assert r_b.status_code == 401, f"Expected 401 for fresh IP B bucket, got {r_b.status_code}"
    log("Proved separate rate limit buckets for different client IPs via X-Forwarded-For!")

    # -------------------------------------------------------------
    # REQUIREMENT 5: JWT VERIFICATION & BLOCKED ACCOUNT CHECK
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 5: JWT VERIFICATION & BLOCKED ACCOUNT CHECK")
    log("=" * 50)
    # Valid authenticated request
    r = requests.get(f"{BASE_URL}/api/v1/campaigns", headers=brand_headers)
    log(f"Active Account Request -> Status: {r.status_code}")
    assert r.status_code == 200

    # Suspend profile and test blocked enforcement
    brand_profile = Profile.objects.get(id=brand_uid)
    brand_profile.status = 'suspended'
    brand_profile.save()

    r = requests.get(f"{BASE_URL}/api/v1/campaigns", headers=brand_headers)
    log(f"Suspended Account Request -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 403
    assert 'suspended' in r.text.lower() or 'blocked' in r.text.lower()

    # Restore profile
    brand_profile.status = 'active'
    brand_profile.save()
    r = requests.get(f"{BASE_URL}/api/v1/campaigns", headers=brand_headers)
    assert r.status_code == 200
    log("Restored active status -> Request returned 200 OK")

    # -------------------------------------------------------------
    # REQUIREMENT 6: TWILIO VERIFY FAIL-CLOSED TEST
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 6: OTP TWILIO VERIFY FAIL-CLOSED TEST (DEV_MODE=False)")
    log("=" * 50)
    orig_dev = settings.DEV_MODE
    try:
        settings.DEV_MODE = False
        res = send_otp("919123456789")
        log(f"send_otp with DEV_MODE=False -> {res}")
        assert res is False, f"Expected send_otp to fail closed (False), got {res}"
        chk = check_otp("919123456789", "123456")
        log(f"check_otp with DEV_MODE=False -> {chk}")
        assert chk is False, f"Expected check_otp to fail closed (False), got {chk}"
        log("OTP correctly failed closed when DEV_MODE=False without Twilio credentials!")
    finally:
        settings.DEV_MODE = orig_dev

    # -------------------------------------------------------------
    # REQUIREMENT 7: MONEY HANDLERS & CONCURRENCY TEST
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 7: MONEY HANDLERS & CONCURRENCY TEST (OrderApproveView)")
    log("=" * 50)

    # Create an order and move it to draft_submitted
    test_creator_obj = Creator.objects.get(id=str(creator_uid))
    order = Order.objects.create(
        id=uuid.uuid4(),
        brand=Profile.objects.get(id=brand_uid),
        creator=test_creator_obj,
        deliverable='Video Reel',
        amount=5000,
        status='draft_submitted',
        revision_count=0,
        draft_url='https://assets.collivra.com/drafts/demo.mp4',
        created_at=django_tz.now(),
        updated_at=django_tz.now(),
    )
    log(f"Created order {order.id} with status 'draft_submitted'")

    # Fire two concurrent approve calls
    results = []
    def call_approve(thread_id):
        r = requests.post(f"{BASE_URL}/api/v1/orders/{order.id}/approve", headers=brand_headers)
        results.append((thread_id, r.status_code, r.json()))

    t1 = threading.Thread(target=call_approve, args=(1,))
    t2 = threading.Thread(target=call_approve, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    for tid, st, data in results:
        log(f"Thread {tid} approve -> Status: {st}, Order Status: {data.get('status')}")
        assert st == 200
        assert data.get('status') == 'released'

    # Verify messages created: exactly 1 release message
    release_msgs = OrderMessage.objects.filter(order_id=order.id, message__icontains='released')
    log(f"Release messages created in database: {release_msgs.count()}")
    assert release_msgs.count() == 1, f"Expected exactly 1 release message, found {release_msgs.count()}"

    # Verify select_bid function integration
    log("\nTesting public.select_bid database function via POST /campaigns/<pk>/bids/<bid_id>/select")
    r = requests.post(f"{BASE_URL}/api/v1/campaigns/{camp_open.id}/bids/{bid_id}/select", headers=brand_headers)
    log(f"Select bid -> Status: {r.status_code}, Body: {r.text}")
    assert r.status_code == 201

    # -------------------------------------------------------------
    # REQUIREMENT 8: DATABASE ROLE PROOF
    # -------------------------------------------------------------
    log("\n" + "=" * 50)
    log("REQUIREMENT 8: DATABASE ROLE PROOF (collivra_app rolsuper = false)")
    log("=" * 50)
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin FROM pg_roles WHERE rolname = 'collivra_app';")
        role_row = cursor.fetchone()
        log(f"collivra_app pg_roles row: {role_row}")
        assert role_row[1] is False, f"collivra_app should have rolsuper=False, got {role_row[1]}"

    log("\nALL PROOFS PASSED SUCCESSFULLY!")

finally:
    cleanup()
