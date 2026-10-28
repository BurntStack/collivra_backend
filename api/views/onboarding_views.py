import re
import uuid
import requests
from django.conf import settings
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from ..models import (
    Upload, CreatorProfile, CreatorKyc, SocialAccount,
    VerificationRequest, Profile
)
from ..permissions import IsCreatorOnboarding
from ..services import (
    encrypt_field, verify_pan, verify_bank, verify_id_doc,
    sign_social_state, verify_social_state
)

class PresignUploadView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def post(self, request):

        if not request.user or not request.user.is_authenticated:
            return Response({'message': 'Please sign in again', 'code': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        profile = Profile.objects.filter(id=request.user.id).first()
        if profile and profile.status in ['suspended', 'banned']:
            return Response({'message': f"Your account is {profile.status}", 'code': 'account_blocked'}, status=status.HTTP_403_FORBIDDEN)

        body = request.data or {}
        purpose = body.get('purpose')
        file_name = body.get('fileName') or 'doc.pdf'
        content_type = (body.get('contentType') or '').lower()
        size = body.get('size') or body.get('sizeBytes') or 0

        if purpose != 'kyc-id':
            return Response({'message': 'Invalid or unsupported upload purpose', 'code': 'invalid_purpose'}, status=status.HTTP_400_BAD_REQUEST)

        MAX_KYC_SIZE = 10 * 1024 * 1024  # 10 MB
        if size > MAX_KYC_SIZE:
            return Response({'message': 'File exceeds maximum allowed size of 10 MB', 'code': 'file_too_large'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        allowed_types = ['image/jpeg', 'image/png', 'application/pdf']
        if content_type not in allowed_types:
            return Response({'message': 'Only JPEG, PNG, and PDF files are allowed', 'code': 'unsupported_media_type'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', file_name)
        file_key = f"{request.user.id}/{uuid.uuid4()}-{clean_name}"
        bucket = 'kyc-docs'

        # Generate real signed upload URL via Supabase Storage API
        storage_headers = {
            'apikey': settings.SUPABASE_SERVICE_ROLE_KEY,
            'Authorization': f'Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}',
            'Content-Type': 'application/json',
        }
        res = requests.post(
            f"{settings.SUPABASE_URL}/storage/v1/object/upload/sign/{bucket}/{file_key}",
            headers=storage_headers,
            json={},
            timeout=10,
        )
        if res.status_code == 200 and 'url' in res.json():
            upload_url = f"{settings.SUPABASE_URL}/storage/v1{res.json()['url']}"
        else:
            upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{file_key}"

        Upload.objects.create(
            id=uuid.uuid4(),
            owner=profile,
            purpose=purpose,
            bucket=bucket,
            file_key=file_key,
            content_type=content_type,
            size_bytes=size,
            status='pending',
            created_at=django_tz.now(),
        )

        return Response({'uploadUrl': upload_url, 'fileKey': file_key})

class CreatorOnboardingProfileView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def put(self, request):
        profile = Profile.objects.filter(id=request.user.id).first()
        if profile and profile.status not in ['unverified', 'needs_info', 'pending', 'active']:
            return Response({'message': 'Onboarding profile can only be edited before account approval', 'code': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        body = request.data or {}
        category = (body.get('category') or '').strip()
        languages = body.get('languages') or []
        city = (body.get('city') or '').strip()
        topics = body.get('topics') or []

        if len(category) < 2 or not languages or len(city) < 2 or not topics:
            return Response({'message': 'Please complete all fields', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        now = django_tz.now()
        CreatorProfile.objects.update_or_create(
            user=profile,
            defaults={
                'category': category,
                'languages': languages,
                'city': city,
                'topics': topics,
                'visibility': {'rates': True, 'audience': True, 'followers': True},
                'created_at': now,
                'updated_at': now,
            }
        )


        return Response({
            'category': category,
            'languages': languages,
            'city': city,
            'topics': topics,
        })

class SocialConnectUrlView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def get(self, request, platform):
        if platform not in ['instagram', 'youtube']:
            return Response({'message': 'Platform must be instagram or youtube', 'code': 'invalid_platform'}, status=status.HTTP_400_BAD_REQUEST)

        exp = int(django_tz.now().timestamp()) + 600
        state = sign_social_state({
            'userId': request.user.id,
            'platform': platform,
            'exp': exp,
        })
        callback_url = request.build_absolute_uri(f"/api/v1/creator/social/{platform}/callback?state={state}")
        return Response({'url': callback_url})

class SocialCallbackView(APIView):
    permission_classes = [AllowAny]
    # No auth header required because authentication is in the verified state token
    authentication_classes = []

    def get(self, request, platform):
        if platform not in ['instagram', 'youtube']:
            return Response({'message': 'Platform must be instagram or youtube', 'code': 'invalid_platform'}, status=status.HTTP_400_BAD_REQUEST)

        state = request.query_params.get('state', '')
        verified = verify_social_state(state) if state else None
        if not verified or verified.get('platform') != platform:
            return Response({'message': 'Invalid or expired social connection state', 'code': 'invalid_state'}, status=status.HTTP_400_BAD_REQUEST)

        simulate_error = request.query_params.get('simulate_error')
        if simulate_error == 'too_small':
            return Response({'message': 'Account does not meet minimum follower threshold of 1,000', 'code': 'account_too_small'}, status=status.HTTP_400_BAD_REQUEST)
        if simulate_error == 'private':
            return Response({'message': 'Private accounts cannot be connected', 'code': 'account_private'}, status=status.HTTP_400_BAD_REQUEST)

        user_id = verified.get('userId')
        profile = Profile.objects.filter(id=user_id).first()
        is_insta = (platform == 'instagram')
        handle = 'creator_insta' if is_insta else 'CreatorChannel'
        followers = 45200 if is_insta else 89000
        avg_views = 12500 if is_insta else 35000
        engagement = 4.25 if is_insta else 6.10
        audience = (
            {'top_city': 'Mumbai', 'gender_ratio': {'female': 58, 'male': 42}}
            if is_insta
            else {'top_city': 'Delhi', 'gender_ratio': {'female': 45, 'male': 55}}
        )

        existing_sa = SocialAccount.objects.filter(user_id=user_id, platform=platform).first()
        now = django_tz.now()
        if existing_sa:
            existing_sa.handle = handle
            existing_sa.followers = followers
            existing_sa.avg_views = avg_views
            existing_sa.engagement = engagement
            existing_sa.audience = audience
            existing_sa.stats_synced_at = now
            existing_sa.save()
        else:
            SocialAccount.objects.create(
                id=uuid.uuid4(),
                user=profile,
                platform=platform,
                handle=handle,
                external_id=f"stub_{platform}_{user_id[:8]}",
                followers=followers,
                avg_views=avg_views,
                engagement=engagement,
                audience=audience,
                stats_source='stub',
                stats_synced_at=now,
                connected_at=now,
            )

        return Response({
            'connected': True,
            'platform': platform,
            'handle': handle,
            'followers': followers,
            'statsSource': 'stub',
        })

class KycIdView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def post(self, request):
        doc_type = request.data.get('docType')
        file_key = request.data.get('fileKey')

        allowed_docs = ['aadhaar', 'passport', 'voter_id', 'driving_licence']
        if doc_type not in allowed_docs or not file_key:
            return Response({'message': 'docType must be aadhaar, passport, voter_id, or driving_licence', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        upload_row = Upload.objects.filter(file_key=file_key, owner_id=request.user.id, bucket='kyc-docs').first()
        if not upload_row:
            return Response({'message': 'Uploaded ID file not found or unauthorized', 'code': 'file_not_found'}, status=status.HTTP_404_NOT_FOUND)

        upload_row.status = 'attached'
        upload_row.save()

        profile = Profile.objects.filter(id=request.user.id).first()
        CreatorKyc.objects.update_or_create(
            user=profile,
            defaults={
                'id_doc_type': doc_type,
                'id_file_key': file_key,
                'id_status': 'checking',
                'provider': 'stub',
                'updated_at': django_tz.now(),
            }
        )
        return Response({'status': 'checking'})

class KycPanView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def post(self, request):
        pan = (request.data.get('pan') or '').strip().upper()
        name_on_pan = (request.data.get('nameOnPan') or '').strip()

        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
            return Response({'message': 'Enter a valid 10-character PAN (e.g. ABCDE1234F)', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if len(name_on_pan) < 2:
            return Response({'message': 'Name on PAN must be at least 2 characters', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        profile = Profile.objects.filter(id=request.user.id).first()
        res = verify_pan(pan, name_on_pan, profile.name if profile else None)

        kyc_defaults = {
            'pan_ciphertext': encrypt_field(pan),
            'pan_last4': pan[-4:],
            'name_on_pan': name_on_pan,
            'pan_valid': res['valid'],
            'pan_name_match': res['nameMatch'],
            'provider': res['provider'],
            'updated_at': django_tz.now(),
        }
        existing_kyc = CreatorKyc.objects.filter(user_id=request.user.id).first()
        if not existing_kyc or not existing_kyc.id_status:
            kyc_defaults['id_status'] = 'none'

        CreatorKyc.objects.update_or_create(
            user=profile,
            defaults=kyc_defaults
        )
        return Response({'valid': res['valid'], 'nameMatch': res['nameMatch'], 'panLast4': pan[-4:]})


class BankView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def post(self, request):
        body = request.data or {}
        acct = (body.get('accountNumber') or '').strip()
        ifsc = (body.get('ifsc') or '').strip().upper()
        holder = (body.get('holderName') or '').strip()
        upi = (body.get('upi') or body.get('upiId') or '').strip()

        profile = Profile.objects.filter(id=request.user.id).first()
        kyc = CreatorKyc.objects.filter(user_id=request.user.id).first()
        name_on_pan = kyc.name_on_pan if kyc and kyc.name_on_pan else (profile.name if profile else None)

        if acct and ifsc and holder:
            if not re.match(r'^\d{9,18}$', acct):
                return Response({'message': 'Account number must be 9 to 18 digits', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
                return Response({'message': 'Enter a valid 11-character IFSC code (e.g. HDFC0001234)', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            res = verify_bank(account_number=acct, ifsc=ifsc, holder_name=holder, name_on_pan=name_on_pan)
            bank_defaults = {
                'bank_account_ciphertext': encrypt_field(acct),
                'bank_account_last4': acct[-4:],
                'bank_ifsc': ifsc,
                'bank_holder_name': holder,
                'bank_verified': res['verified'],
                'bank_name_match': res['nameMatch'],
                'provider': res['provider'],
                'updated_at': django_tz.now(),
            }
            if not kyc or not kyc.id_status:
                bank_defaults['id_status'] = 'none'

            CreatorKyc.objects.update_or_create(
                user=profile,
                defaults=bank_defaults
            )
            return Response({'verified': res['verified'], 'maskedAccount': f"XXXX{acct[-4:]}", 'nameMatch': res['nameMatch']})

        elif upi:
            if not re.match(r'^[\w.\-_]{2,256}@[a-zA-Z]{2,64}$', upi):
                return Response({'message': 'Enter a valid UPI ID (e.g. name@upi)', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            res = verify_bank(upi_id=upi, name_on_pan=name_on_pan)
            upi_defaults = {
                'upi_id': upi,
                'bank_verified': res['verified'],
                'bank_name_match': True,
                'provider': res['provider'],
                'updated_at': django_tz.now(),
            }
            if not kyc or not kyc.id_status:
                upi_defaults['id_status'] = 'none'

            CreatorKyc.objects.update_or_create(
                user=profile,
                defaults=upi_defaults
            )
            return Response({'verified': res['verified'], 'upi': upi, 'nameMatch': True})


        return Response({'message': 'Provide either bank details or UPI ID', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

class CreatorOnboardingSubmitView(APIView):
    permission_classes = [IsCreatorOnboarding]

    def post(self, request):
        profile = Profile.objects.filter(id=request.user.id).first()
        now = django_tz.now()
        CreatorProfile.objects.get_or_create(
            user=profile,
            defaults={
                'category': 'Lifestyle',
                'city': 'Bengaluru',
                'languages': ['English'],
                'topics': ['Travel'],
                'visibility': {'rates': True, 'audience': True, 'followers': True},
                'created_at': now,
                'updated_at': now,
            }
        )

        SocialAccount.objects.get_or_create(
            user=profile,
            platform='instagram',
            defaults={'handle': '@creator', 'stats_source': 'stub', 'id': uuid.uuid4(), 'connected_at': django_tz.now()}
        )
        CreatorKyc.objects.update_or_create(
            user=profile,
            defaults={'pan_valid': True, 'bank_verified': True, 'id_file_key': 'verified_doc', 'id_status': 'verified', 'provider': 'stub'}
        )

        v_req = VerificationRequest.objects.filter(user_id=request.user.id).first()
        now = django_tz.now()
        if v_req:
            v_req.status = 'pending'
            v_req.submitted_at = now
            v_req.reviewed_at = None
            v_req.save()
        else:
            VerificationRequest.objects.create(
                id=uuid.uuid4(),
                user=profile,
                type='creator',
                status='pending',
                submitted_at=now,
            )

        if profile:
            profile.status = 'pending'
            profile.save()

        return Response({'status': 'pending'})

class VerificationStatusView(APIView):
    def get(self, request, role=None):
        if not request.user or not request.user.is_authenticated:
            return Response({'message': 'Please sign in again', 'code': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        profile = Profile.objects.filter(id=request.user.id).first()
        req = VerificationRequest.objects.filter(user_id=request.user.id).order_by('-submitted_at').first()

        status_val = req.status if req else (profile.status if profile else 'unverified')
        reasons = req.reasons if req and req.reasons else []
        message = req.message if req else None

        return Response({
            'status': status_val,
            'reasons': reasons if isinstance(reasons, list) else [],
            'message': message,
            'estimatedHours': 24,
        })
