import os
import sys
import uuid
import django

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone as django_tz
from rest_framework.test import APIClient
from api.models import Profile, BrandProfiles
from api.authentication import SupabaseUser


def run_tests():
    print("=" * 60)
    print("STARTING BRAND ONBOARDING WORKFLOW VERIFICATION")
    print("=" * 60)

    client = APIClient()

    # 1. Test unauthenticated request
    print("\n--- 1. Testing Unauthenticated Request ---")
    res = client.get('/api/v1/brand/onboarding')
    print("Unauth GET status:", res.status_code)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"

    res = client.post('/api/v1/brand/onboarding', {'brandName': 'Test'}, format='json')
    print("Unauth POST status:", res.status_code)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print(" Unauthenticated requests correctly rejected (401).")

    from api.services import supabase_auth

    # Setup real Supabase test user
    test_id = uuid.uuid4().hex[:6]
    test_email = f"brand_onboarding_{test_id}@collivra.test"
    test_password = "SecurePassword123!"

    signup_res = supabase_auth.create_user(
        email=test_email,
        password=test_password,
        user_metadata={"role": "brand", "name": f"Pending Brand {test_id}"}
    )
    assert signup_res.status_code in (200, 201), f"Signup failed: {signup_res.text}"
    test_user_id = signup_res.json()['id']

    # Fetch profile created by trigger
    profile = Profile.objects.filter(id=test_user_id).first()
    assert profile is not None, "Profile was not created by trigger"
    profile.is_profile_completed = False
    profile.save()
    print(f"\nCreated initial test user (id: {test_user_id}, email: {test_email})")

    auth_user = SupabaseUser(
        user_id=test_user_id,
        email=test_email,
        role='brand',
        status='unverified',
        raw_claims={'sub': str(test_user_id), 'email': test_email}
    )
    client.force_authenticate(user=auth_user)

    # 2. Validation Errors
    print("\n--- 2. Testing Field Validation ---")
    # 2a. Missing required brand_name
    bad_payload = {
        'regionState': 'Karnataka',
        'businessCategory': 'Fashion & Style',
        'geographicalScope': 'Within City',
        'termsAccepted': True
    }
    res = client.post('/api/v1/brand/onboarding', bad_payload, format='json')
    print("Missing brand_name status:", res.status_code)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"
    assert 'brand_name' in res.json().get('errors', {}), "Expected brand_name validation error"

    # 2b. Invalid business category
    bad_cat_payload = {
        'brandName': 'StyleHub',
        'regionState': 'Karnataka',
        'businessCategory': 'Crypto & Web3',  # Invalid choice
        'geographicalScope': 'Within City',
        'termsAccepted': True
    }
    res = client.post('/api/v1/brand/onboarding', bad_cat_payload, format='json')
    print("Invalid category status:", res.status_code)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"

    # 2c. Terms not accepted
    unaccepted_terms = {
        'brandName': 'StyleHub',
        'regionState': 'Karnataka',
        'businessCategory': 'Fashion & Style',
        'geographicalScope': 'Within City',
        'termsAccepted': False
    }
    res = client.post('/api/v1/brand/onboarding', unaccepted_terms, format='json')
    print("Unaccepted terms status:", res.status_code)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"
    print(" Validation checks passed perfectly (422 for invalid payloads).")

    # 3. Successful Brand Onboarding Submission
    print("\n--- 3. Testing Valid Brand Onboarding Submission ---")
    valid_payload = {
        'firstName': 'Pooja',
        'lastName': 'Hegde',
        'brandName': 'Silk & Soul Apparel',
        'brandLogo': 'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9',
        'brandWebsite': 'silksoul.in',
        'country': 'India',
        'regionState': 'Karnataka',
        'city': 'Bengaluru',
        'mobile': '+919876512345',
        'businessCategory': 'Fashion & Style',
        'geographicalScope': 'Across Country',
        'termsAccepted': True
    }
    res = client.post('/api/v1/brand/onboarding', valid_payload, format='json')
    print("Valid submission status:", res.status_code)
    print("Response payload:", res.json())
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    assert body.get('ok') is True
    assert body.get('user', {}).get('isProfileCompleted') is True
    assert body.get('user', {}).get('role') == 'brand'
    assert body.get('brandProfile', {}).get('brandName') == 'Silk & Soul Apparel'
    assert body.get('brandProfile', {}).get('businessCategory') == 'Fashion & Style'

    # Verify Database state
    profile.refresh_from_db()
    assert profile.is_profile_completed is True, "Profile is_profile_completed must be True"
    assert profile.role == 'brand', "Profile role must be 'brand'"
    assert profile.company_name == 'Silk & Soul Apparel'
    assert profile.name == 'Pooja Hegde'
    assert profile.status == 'active'

    bp = BrandProfiles.objects.filter(user=profile).first()
    assert bp is not None, "BrandProfile record must exist"
    assert bp.brand_name == 'Silk & Soul Apparel'
    assert bp.region_state == 'Karnataka'
    assert bp.city == 'Bengaluru'
    assert bp.business_category == 'Fashion & Style'
    assert bp.geographical_scope == 'Across Country'
    assert bp.terms_accepted is True
    print(" Database records verified: is_profile_completed flipped to True!")

    # 4. Testing GET Brand Onboarding
    print("\n--- 4. Testing GET Brand Onboarding Profile ---")
    res_get = client.get('/api/v1/brand/onboarding')
    print("GET status:", res_get.status_code)
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data.get('brandProfile', {}).get('city') == 'Bengaluru'
    print(" GET endpoint successfully fetched saved brand profile.")

    # 5. Testing PUT Update
    print("\n--- 5. Testing PUT Brand Onboarding Update ---")
    update_payload = {
        'firstName': 'Pooja',
        'lastName': 'Hegde',
        'brandName': 'Silk & Soul Global',
        'regionState': 'Maharashtra',
        'city': 'Mumbai',
        'businessCategory': 'Fashion & Style',
        'geographicalScope': 'International',
        'termsAccepted': True
    }
    res_put = client.put('/api/v1/brand/onboarding/profile', update_payload, format='json')
    print("PUT status:", res_put.status_code)
    assert res_put.status_code == 200
    bp.refresh_from_db()
    assert bp.brand_name == 'Silk & Soul Global'
    assert bp.city == 'Mumbai'
    assert bp.geographical_scope == 'International'
    print(" PUT updates applied cleanly.")

    # Clean up test data
    BrandProfiles.objects.filter(user=profile).delete()
    supabase_auth.delete_user(str(test_user_id))
    print("\n--- CLEANUP COMPLETE ---")
    print("ALL BRAND ONBOARDING TESTS PASSED 100% PERFECTLY!")


if __name__ == '__main__':
    run_tests()
