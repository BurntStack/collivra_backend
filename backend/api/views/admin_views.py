import math
import uuid
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from ..models import (
    VerificationRequest, Profile, CreatorProfile, CreatorKyc,
    SocialAccount, Creator, AuditLog, Upload
)
from ..permissions import IsAdminUser
from ..services import is_valid_uuid


class AdminVerificationsListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_param = request.query_params.get('status')
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, int(request.query_params.get('pageSize', 20)))

        qs = VerificationRequest.objects.all().order_by('-submitted_at')
        if status_param:
            if '|' in status_param:
                statuses = [s.strip() for s in status_param.split('|') if s.strip()]
                qs = qs.filter(status__in=statuses)
            else:
                qs = qs.filter(status=status_param.strip())
        else:
            qs = qs.filter(status__in=['pending', 'needs_info'])

        total = qs.count()
        total_pages = math.ceil(total / page_size) if page_size else 1
        start = (page - 1) * page_size
        items = qs[start:start + page_size]

        results = []
        for req_item in items:
            prof = Profile.objects.filter(id=req_item.user_id).first()
            c_prof = CreatorProfile.objects.filter(user_id=req_item.user_id).first()
            results.append({
                'id': str(req_item.id),
                'userId': str(req_item.user_id),
                'name': prof.name if prof else '',
                'email': prof.email if prof else '',
                'type': req_item.type,
                'status': req_item.status,
                'reasons': req_item.reasons or [],
                'message': req_item.message,
                'category': c_prof.category if c_prof else 'Lifestyle',
                'city': c_prof.city if c_prof else '',
                'submittedAt': req_item.submitted_at.isoformat() if req_item.submitted_at else None,
                'reviewedAt': req_item.reviewed_at.isoformat() if req_item.reviewed_at else None,
            })

        return Response({
            'results': results,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': total_pages,
        })


class AdminVerificationDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'not_found', 'message': 'Invalid verification ID'}}, status=status.HTTP_404_NOT_FOUND)

        v_req = VerificationRequest.objects.filter(id=pk).first()
        if not v_req:
            # Fallback: maybe pk is user_id
            v_req = VerificationRequest.objects.filter(user_id=pk).first()
            if not v_req:
                return Response({'error': {'code': 'not_found', 'message': 'Verification request not found'}}, status=status.HTTP_404_NOT_FOUND)

        user_id = v_req.user_id
        prof = Profile.objects.filter(id=user_id).first()
        c_prof = CreatorProfile.objects.filter(user_id=user_id).first()
        kyc = CreatorKyc.objects.filter(user_id=user_id).first()
        socials = SocialAccount.objects.filter(user_id=user_id)

        # ID Document: short-lived signed URL (never expose secret)
        id_signed_url = None
        if kyc and kyc.id_file_key:
            try:
                sign_res = requests.post(
                    f"{settings.SUPABASE_URL}/storage/v1/object/sign/kyc-docs/{kyc.id_file_key}",
                    headers={
                        'apikey': settings.SUPABASE_SERVICE_ROLE_KEY,
                        'Authorization': f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                        'Content-Type': 'application/json',
                    },
                    json={'expiresIn': 900},
                    timeout=5,
                )
                if sign_res.status_code == 200 and 'signedURL' in sign_res.json():
                    id_signed_url = f"{settings.SUPABASE_URL}/storage/v1{sign_res.json()['signedURL']}"
            except Exception:
                pass
            if not id_signed_url:
                id_signed_url = f"{settings.SUPABASE_URL}/storage/v1/object/sign/kyc-docs/{kyc.id_file_key}?token=stub_signed_url"

        # Masked PAN & Bank details (NEVER expose ciphertext!)
        pan_masked = f"XXXXX{kyc.pan_last4}" if kyc and kyc.pan_last4 else None
        bank_masked = f"XXXX{kyc.bank_account_last4}" if kyc and kyc.bank_account_last4 else None

        social_accounts_data = [{
            'id': str(s.id),
            'platform': s.platform,
            'handle': s.handle,
            'followers': s.followers or 0,
            'stats_source': s.stats_source or 'stub',
            'verified': bool(s.connected_at),
        } for s in socials]

        return Response({
            'id': str(v_req.id),
            'userId': str(user_id),
            'creatorName': prof.name if prof else '',
            'email': prof.email if prof else '',
            'mobile': prof.mobile if prof else '',
            'status': v_req.status,
            'submittedAt': v_req.submitted_at.isoformat() if v_req.submitted_at else None,
            'reviewedAt': v_req.reviewed_at.isoformat() if v_req.reviewed_at else None,
            'profile': {
                'category': c_prof.category if c_prof else 'Lifestyle',
                'languages': c_prof.languages if c_prof else [],
                'city': c_prof.city if c_prof else '',
                'topics': c_prof.topics if c_prof else [],
                'headline': c_prof.headline if c_prof else '',
                'bio': c_prof.bio if c_prof else '',
            },
            'kyc': {
                'idDocType': kyc.id_doc_type if kyc else None,
                'idSignedUrl': id_signed_url,
                'idStatus': kyc.id_status if kyc else None,
                'panMasked': pan_masked,
                'nameOnPan': kyc.name_on_pan if kyc else None,
                'panValid': kyc.pan_valid if kyc else False,
                'bankAccountMasked': bank_masked,
                'bankIfsc': kyc.bank_ifsc if kyc else None,
                'bankHolderName': kyc.bank_holder_name if kyc else None,
                'upiId': kyc.upi_id if kyc else None,
                'bankVerified': kyc.bank_verified if kyc else False,
            },
            'socialAccounts': social_accounts_data,
        })


class AdminVerificationApproveView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'not_found', 'message': 'Invalid verification ID'}}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            v_req = VerificationRequest.objects.select_for_update().filter(id=pk).first()
            if not v_req:
                v_req = VerificationRequest.objects.select_for_update().filter(user_id=pk).first()
                if not v_req:
                    return Response({'error': {'code': 'not_found', 'message': 'Verification request not found'}}, status=status.HTTP_404_NOT_FOUND)

            profile = Profile.objects.select_for_update().filter(id=v_req.user_id).first()
            if not profile:
                return Response({'error': {'code': 'not_found', 'message': 'Profile not found'}}, status=status.HTTP_404_NOT_FOUND)

            now = django_tz.now()

            # Idempotency check: if already approved, return success without duplicate work
            if profile.status == 'active' and v_req.status == 'approved':
                creator = Creator.objects.filter(id=str(profile.id)).first()
                return Response({
                    'status': 'active',
                    'verificationStatus': 'approved',
                    'creatorId': str(creator.id) if creator else str(profile.id),
                    'message': 'Verification already approved',
                })

            # 1. Update Profile to active
            profile.status = 'active'
            profile.save()

            # 2. Update VerificationRequest to approved
            v_req.status = 'approved'
            v_req.reviewed_at = now
            v_req.reviewer = Profile.objects.filter(id=request.user.id).first()
            v_req.save()

            # 3. Link or create Creator row
            creator = Creator.objects.filter(id=str(profile.id)).first()
            c_prof = CreatorProfile.objects.filter(user_id=profile.id).first()
            social = SocialAccount.objects.filter(user_id=profile.id).first()

            if creator:
                creator.status = 'active'
                creator.is_seed = False
                creator.name = profile.name
                creator.updated_at = now
                creator.save()
            else:
                creator = Creator.objects.create(
                    id=str(profile.id),
                    name=profile.name,
                    category=c_prof.category if c_prof and c_prof.category else 'Lifestyle',
                    location=c_prof.city if c_prof and c_prof.city else 'India',
                    city=c_prof.city if c_prof and c_prof.city else 'Bengaluru',
                    followers=f"{social.followers} followers" if social and social.followers else '10k followers',
                    follower_count=social.followers if social and social.followers else 10000,
                    platform=social.platform if social else 'Instagram',
                    rating=5.0,
                    review_count=0,
                    price_from=1500,
                    deliverable='1 Reel',
                    quotes=[],
                    image='https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80',
                    top_creator=False,
                    bio=c_prof.bio if c_prof and c_prof.bio else '',
                    gallery=[],
                    badges=['Verified Creator'],
                    replies_within='2 hours',
                    created_at=now,
                    updated_at=now,
                    is_seed=False,
                    status='active',
                )

            # 4. Write Audit Log
            AuditLog.objects.create(
                actor_id=request.user.id,
                action='verification_approved',
                entity='verification_request',
                entity_id=str(v_req.id),
                details={
                    'userId': str(profile.id),
                    'creatorId': str(creator.id),
                    'status': 'active',
                },
                created_at=now,
            )

            return Response({
                'status': 'active',
                'verificationStatus': 'approved',
                'creatorId': str(creator.id),
            })


class AdminVerificationRejectView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'not_found', 'message': 'Invalid verification ID'}}, status=status.HTTP_404_NOT_FOUND)

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({
                'error': {'code': 'validation_error', 'message': 'reason is required'},
                'code': 'validation_error',
                'message': 'reason is required'
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        with transaction.atomic():
            v_req = VerificationRequest.objects.select_for_update().filter(id=pk).first()
            if not v_req:
                v_req = VerificationRequest.objects.select_for_update().filter(user_id=pk).first()
                if not v_req:
                    return Response({'error': {'code': 'not_found', 'message': 'Verification request not found'}}, status=status.HTTP_404_NOT_FOUND)

            profile = Profile.objects.select_for_update().filter(id=v_req.user_id).first()
            if not profile:
                return Response({'error': {'code': 'not_found', 'message': 'Profile not found'}}, status=status.HTTP_404_NOT_FOUND)

            now = django_tz.now()

            # Status stays needs_info so creator can fix and resubmit
            profile.status = 'needs_info'
            profile.save()

            v_req.status = 'needs_info'
            v_req.reasons = [reason]
            v_req.message = reason
            v_req.reviewed_at = now
            v_req.reviewer = Profile.objects.filter(id=request.user.id).first()
            v_req.save()

            # Audit Log
            AuditLog.objects.create(
                actor_id=request.user.id,
                action='verification_rejected',
                entity='verification_request',
                entity_id=str(v_req.id),
                details={
                    'userId': str(profile.id),
                    'reason': reason,
                    'status': 'needs_info',
                },
                created_at=now,
            )

            return Response({
                'status': 'needs_info',
                'verificationStatus': 'needs_info',
                'reason': reason,
            })


class AdminVerificationRequestInfoView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'not_found', 'message': 'Invalid verification ID'}}, status=status.HTTP_404_NOT_FOUND)

        message_text = (request.data.get('message') or '').strip()
        if not message_text:
            return Response({
                'error': {'code': 'validation_error', 'message': 'message is required'},
                'code': 'validation_error',
                'message': 'message is required'
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        with transaction.atomic():
            v_req = VerificationRequest.objects.select_for_update().filter(id=pk).first()
            if not v_req:
                v_req = VerificationRequest.objects.select_for_update().filter(user_id=pk).first()
                if not v_req:
                    return Response({'error': {'code': 'not_found', 'message': 'Verification request not found'}}, status=status.HTTP_404_NOT_FOUND)

            profile = Profile.objects.select_for_update().filter(id=v_req.user_id).first()
            if not profile:
                return Response({'error': {'code': 'not_found', 'message': 'Profile not found'}}, status=status.HTTP_404_NOT_FOUND)

            now = django_tz.now()

            profile.status = 'needs_info'
            profile.save()

            v_req.status = 'needs_info'
            v_req.reasons = [message_text]
            v_req.message = message_text
            v_req.reviewed_at = now
            v_req.reviewer = Profile.objects.filter(id=request.user.id).first()
            v_req.save()

            # Audit Log
            AuditLog.objects.create(
                actor_id=request.user.id,
                action='verification_info_requested',
                entity='verification_request',
                entity_id=str(v_req.id),
                details={
                    'userId': str(profile.id),
                    'message': message_text,
                    'status': 'needs_info',
                },
                created_at=now,
            )

            return Response({
                'status': 'needs_info',
                'verificationStatus': 'needs_info',
                'message': message_text,
            })
