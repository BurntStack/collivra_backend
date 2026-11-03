import math
import uuid
from django.db import transaction
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import AuditLog, CreatorProfiles, Profile
from ...permissions import IsAdminUser
from ...services import is_valid_uuid, supabase_auth


def serialize_creator_in_queue(cp):
    user = cp.user
    return {
        'userId': str(user.id),
        'name': user.name,
        'firstName': cp.first_name,
        'lastName': cp.last_name,
        'email': user.email,
        'mobile': user.mobile,
        'dob': cp.dob.isoformat() if cp.dob else None,
        'gender': cp.gender,
        'category': cp.category,
        'bio': cp.bio,
        'languages': cp.languages or [],
        'city': cp.city,
        'regionState': cp.region_state,
        'country': cp.country,
        'instagramHandle': cp.instagram_handle,
        'youtubeHandle': cp.youtube_handle,
        'tiktokHandle': cp.tiktok_handle,
        'socialLinks': cp.social_links or {},
        'panNumber': cp.pan_number,
        'kycStatus': cp.kyc_status,
        'approvalStatus': cp.approval_status,
        'isProfileCompleted': user.is_profile_completed,
        'submittedAt': cp.updated_at.isoformat() if cp.updated_at else None,
        'createdAt': cp.created_at.isoformat() if cp.created_at else None,
    }


class CreatorVerificationQueueView(APIView):
    """
    Superadmin view listing creator onboarding profiles awaiting verification.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get('status', 'pending').strip().lower()
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, min(100, int(request.query_params.get('pageSize', 20))))

        qs = CreatorProfiles.objects.select_related('user').all()
        if status_filter != 'all':
            qs = qs.filter(approval_status=status_filter)

        qs = qs.order_by('-updated_at')
        total = qs.count()

        start = (page - 1) * page_size
        end = start + page_size
        items = [serialize_creator_in_queue(cp) for cp in qs[start:end]]

        return Response({
            'items': items,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': math.ceil(total / page_size) if total > 0 else 1,
            'statusFilter': status_filter,
        }, status=status.HTTP_200_OK)


class CreatorApproveView(APIView):
    """
    Superadmin view to approve a creator profile.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response(
                {'error': {'code': 'invalid_id', 'message': 'Invalid creator user ID'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        creator_profile = CreatorProfiles.objects.select_related('user').filter(user_id=pk).first()
        if not creator_profile:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Creator profile not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        now = django_tz.now()
        with transaction.atomic():
            creator_profile.approval_status = 'approved'
            if creator_profile.pan_number:
                creator_profile.kyc_status = 'verified'
            creator_profile.updated_at = now
            creator_profile.save()

            user = creator_profile.user
            user.approval_status = 'approved'
            user.status = 'active'
            user.updated_at = now
            user.save()

            # Write Audit Log
            AuditLog.objects.create(
                actor_id=request.user.id,
                action='creator_approved',
                entity='creator_profile',
                entity_id=str(user.id),
                details={
                    'approved_by': getattr(request.user, 'email', str(request.user.id)),
                    'creator_name': user.name,
                    'creator_email': user.email,
                },
                created_at=now,
            )

        # Sync with Supabase Auth
        try:
            supabase_auth.update_user_metadata(str(user.id), {
                'approval_status': 'approved',
                'status': 'active',
            })
        except Exception:
            pass

        return Response({
            'ok': True,
            'message': f'Creator {user.name or user.email} has been approved successfully.',
            'creator': serialize_creator_in_queue(creator_profile),
        }, status=status.HTTP_200_OK)


class CreatorRejectView(APIView):
    """
    Superadmin view to reject a creator profile.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response(
                {'error': {'code': 'invalid_id', 'message': 'Invalid creator user ID'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        creator_profile = CreatorProfiles.objects.select_related('user').filter(user_id=pk).first()
        if not creator_profile:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Creator profile not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        reason = (request.data.get('reason') or request.data.get('message') or 'Application rejected by administrator').strip()
        now = django_tz.now()

        with transaction.atomic():
            creator_profile.approval_status = 'rejected'
            creator_profile.kyc_status = 'rejected'
            creator_profile.updated_at = now
            creator_profile.save()

            user = creator_profile.user
            user.approval_status = 'rejected'
            user.updated_at = now
            user.save()

            # Write Audit Log
            AuditLog.objects.create(
                actor_id=request.user.id,
                action='creator_rejected',
                entity='creator_profile',
                entity_id=str(user.id),
                details={
                    'rejected_by': getattr(request.user, 'email', str(request.user.id)),
                    'reason': reason,
                    'creator_name': user.name,
                    'creator_email': user.email,
                },
                created_at=now,
            )

        # Sync with Supabase Auth
        try:
            supabase_auth.update_user_metadata(str(user.id), {
                'approval_status': 'rejected',
            })
        except Exception:
            pass

        return Response({
            'ok': True,
            'message': f'Creator {user.name or user.email} has been rejected.',
            'reason': reason,
            'creator': serialize_creator_in_queue(creator_profile),
        }, status=status.HTTP_200_OK)
