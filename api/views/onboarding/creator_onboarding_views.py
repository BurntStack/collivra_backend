from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import CreatorProfiles, Profile
from ...services import supabase_auth
from ..auth.common import format_user_payload
from .serializers import CreatorOnboardingSerializer


def format_creator_profile(cp):
    if not cp:
        return None
    return {
        'firstName': cp.first_name,
        'lastName': cp.last_name,
        'dob': cp.dob.isoformat() if cp.dob else None,
        'gender': cp.gender,
        'category': cp.category,
        'bio': cp.bio,
        'languages': cp.languages or [],
        'city': cp.city,
        'regionState': cp.region_state,
        'country': cp.country or 'India',
        'instagramHandle': cp.instagram_handle,
        'youtubeHandle': cp.youtube_handle,
        'tiktokHandle': cp.tiktok_handle,
        'socialLinks': cp.social_links or {},
        'panNumber': cp.pan_number,
        'kycStatus': cp.kyc_status,
        'approvalStatus': cp.approval_status,
        'updatedAt': cp.updated_at.isoformat() if cp.updated_at else None,
    }


class CreatorOnboardingView(APIView):
    """
    Onboarding workflow endpoint for Creators.
    GET: Retrieves the current user's CreatorProfile.
    POST / PUT: Validates and saves creator details, enforces age 18+, sets approval_status='pending', and flips is_profile_completed=True.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile:
            return Response(
                {'error': {'code': 'not_found', 'message': 'User profile not found'}, 'code': 'not_found'},
                status=status.HTTP_404_NOT_FOUND
            )

        creator_profile = CreatorProfiles.objects.filter(user=profile).first()
        return Response({
            'ok': True,
            'user': format_user_payload(profile),
            'creatorProfile': format_creator_profile(creator_profile)
        }, status=status.HTTP_200_OK)

    def post(self, request):
        return self._save_creator_onboarding(request)

    def put(self, request):
        return self._save_creator_onboarding(request)

    def _save_creator_onboarding(self, request):
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

        serializer = CreatorOnboardingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': {
                        'code': 'validation_error',
                        'message': 'Invalid creator onboarding details provided.',
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
        dob = validated.get('dob')
        gender = validated.get('gender')
        category = (validated.get('category') or '').strip()
        bio = (validated.get('bio') or '').strip()
        languages = validated.get('languages') or []
        city = (validated.get('city') or '').strip()
        region_state = (validated.get('region_state') or '').strip()
        country = (validated.get('country') or 'India').strip()

        instagram_handle = validated.get('instagram_handle')
        youtube_handle = validated.get('youtube_handle')
        tiktok_handle = validated.get('tiktok_handle')
        social_links = validated.get('social_links') or {}

        # Merge handles into social_links dict
        if instagram_handle and 'instagram' not in social_links:
            social_links['instagram'] = f"https://instagram.com/{instagram_handle}"
        if youtube_handle and 'youtube' not in social_links:
            social_links['youtube'] = f"https://youtube.com/@{youtube_handle}"
        if tiktok_handle and 'tiktok' not in social_links:
            social_links['tiktok'] = f"https://tiktok.com/@{tiktok_handle}"

        pan_number = validated.get('pan_number')
        kyc_status = 'verified'

        now = django_tz.now()

        # 1. Update or create CreatorProfile
        creator_profile, _ = CreatorProfiles.objects.update_or_create(
            user=profile,
            defaults={
                'first_name': first_name or None,
                'last_name': last_name or None,
                'dob': dob,
                'gender': gender or None,
                'category': category or None,
                'bio': bio or None,
                'languages': languages,
                'city': city,
                'region_state': region_state,
                'country': country,
                'instagram_handle': instagram_handle,
                'youtube_handle': youtube_handle,
                'tiktok_handle': tiktok_handle,
                'social_links': social_links,
                'pan_number': pan_number,
                'kyc_status': kyc_status,
                'approval_status': 'approved',
                'updated_at': now,
            }
        )

        # 2. Update core user Profile
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            profile.name = full_name
        profile.role = 'creator'
        profile.status = 'active'
        profile.is_profile_completed = True
        profile.approval_status = 'approved'
        profile.updated_at = now
        profile.save()

        # 3. Sync to Supabase user metadata
        try:
            supabase_auth.update_user_metadata(str(profile.id), {
                'role': 'creator',
                'name': profile.name,
                'status': 'active',
                'approval_status': 'approved',
                'is_profile_completed': True,
            })
        except Exception:
            pass

        return Response({
            'ok': True,
            'message': 'Creator profile completed successfully.',
            'user': format_user_payload(profile),
            'creatorProfile': format_creator_profile(creator_profile),
        }, status=status.HTTP_200_OK)

