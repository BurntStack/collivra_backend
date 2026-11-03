from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import BrandProfiles, Profile
from ...services import supabase_auth
from ..auth.common import format_user_payload
from .serializers import BrandOnboardingSerializer


def format_brand_profile(bp):
    if not bp:
        return None
    return {
        'firstName': bp.first_name,
        'lastName': bp.last_name,
        'brandName': bp.brand_name or bp.company_name,
        'brandLogo': bp.brand_logo,
        'brandWebsite': bp.brand_website,
        'country': bp.country or 'India',
        'regionState': bp.region_state,
        'city': bp.city,
        'mobile': bp.mobile,
        'businessCategory': bp.business_category,
        'geographicalScope': bp.geographical_scope,
        'termsAccepted': bp.terms_accepted,
        'updatedAt': bp.updated_at.isoformat() if bp.updated_at else None,
    }


class BrandOnboardingView(APIView):
    """
    Onboarding workflow endpoint for Brands.
    GET: Retrieves the current user's BrandProfile.
    POST / PUT: Validates and saves brand details, flips is_profile_completed=True, and sets role='brand'.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile:
            return Response(
                {'error': {'code': 'not_found', 'message': 'User profile not found'}, 'code': 'not_found'},
                status=status.HTTP_404_NOT_FOUND
            )

        brand_profile = BrandProfiles.objects.filter(user=profile).first()
        return Response({
            'ok': True,
            'user': format_user_payload(profile),
            'brandProfile': format_brand_profile(brand_profile)
        }, status=status.HTTP_200_OK)

    def post(self, request):
        return self._save_brand_onboarding(request)

    def put(self, request):
        return self._save_brand_onboarding(request)

    def _save_brand_onboarding(self, request):
        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile:
            return Response(
                {'error': {'code': 'not_found', 'message': 'User profile not found'}, 'code': 'not_found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if profile.status in ['suspended', 'banned']:
            return Response(
                {'error': {'code': 'account_blocked', 'message': f'Your account is {profile.status}'}},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BrandOnboardingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': {
                        'code': 'validation_error',
                        'message': 'Invalid onboarding details provided.',
                        'details': serializer.errors,
                    },
                    'errors': serializer.errors,
                    'code': 'validation_error',
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        validated = serializer.validated_data
        first_name = (validated.get('first_name') or '').strip()
        last_name = (validated.get('last_name') or '').strip()
        brand_name = (validated.get('brand_name') or '').strip()
        brand_logo = (validated.get('brand_logo') or '').strip()
        brand_website = (validated.get('brand_website') or '').strip()
        country = (validated.get('country') or 'India').strip()
        region_state = (validated.get('region_state') or '').strip()
        city = (validated.get('city') or '').strip()
        mobile = (validated.get('mobile') or '').strip()
        business_category = validated.get('business_category')
        geographical_scope = validated.get('geographical_scope')
        terms_accepted = bool(validated.get('terms_accepted'))

        now = django_tz.now()

        # 1. Update or create BrandProfile
        brand_profile, _ = BrandProfiles.objects.update_or_create(
            user=profile,
            defaults={
                'first_name': first_name or None,
                'last_name': last_name or None,
                'brand_name': brand_name,
                'company_name': brand_name,
                'brand_logo': brand_logo or None,
                'brand_website': brand_website or None,
                'country': country,
                'region_state': region_state,
                'city': city or None,
                'mobile': mobile or profile.mobile,
                'business_category': business_category,
                'geographical_scope': geographical_scope,
                'terms_accepted': terms_accepted,
                'updated_at': now,
            }
        )

        # 2. Update core user Profile
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            profile.name = full_name
        profile.role = 'brand'
        profile.company_name = brand_name
        profile.is_profile_completed = True
        profile.status = 'active'
        if mobile and not profile.mobile:
            profile.mobile = mobile
        if terms_accepted and not profile.terms_accepted_at:
            profile.terms_accepted_at = now
            profile.terms_version = 'v1.0'
        profile.updated_at = now
        profile.save()

        # 3. Best effort sync to Supabase Auth user metadata
        try:
            supabase_auth.update_user_metadata(str(profile.id), {
                'role': 'brand',
                'name': profile.name,
                'company_name': brand_name,
                'is_profile_completed': True,
                'status': 'active',
            })
        except Exception:
            pass

        return Response({
            'ok': True,
            'message': 'Brand onboarding profile completed successfully.',
            'user': format_user_payload(profile),
            'brandProfile': format_brand_profile(brand_profile),
        }, status=status.HTTP_200_OK)

