import uuid
from datetime import datetime, timezone, timedelta
from django.db import transaction, IntegrityError, connection, DatabaseError
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ..models import Campaign, CampaignBid, Order, Creator, Profile, CreatorProfile
from ..permissions import IsBrandUser, IsCreatorUser
from ..services import is_valid_uuid

class CampaignListCreateView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request):
        body = request.data or {}
        title = (body.get('title') or '').strip()
        platform = (body.get('platform') or 'Instagram').strip()
        deliverables = (body.get('deliverables') or body.get('requirements') or '').strip()
        budget_min = body.get('budgetMin')
        budget_max = body.get('budgetMax')

        if budget_max is None and 'budget' in body:
            try:
                b_val = int(body.get('budget'))
                if budget_min is None:
                    budget_min = 0
                budget_max = b_val
            except (ValueError, TypeError):
                pass
        elif budget_min is None and budget_max is not None:
            budget_min = 0

        apply_by = (body.get('applyBy') or '').strip()
        if not apply_by:
            apply_by = (django_tz.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        brief = (body.get('brief') or '').strip()
        camp_status = body.get('status', 'open_for_bids')

        fields = {}
        if len(title) < 3:
            fields['title'] = 'Title is required'
        if not platform:
            fields['platform'] = 'Platform is required'
        if not deliverables:
            fields['deliverables'] = 'Deliverables are required'
        if not isinstance(budget_min, int) or budget_min < 0:
            fields['budgetMin'] = 'budgetMin must be a non-negative integer'
        if not isinstance(budget_max, int) or budget_max <= 0:
            fields['budgetMax'] = 'budgetMax must be a positive integer'
        if isinstance(budget_min, int) and isinstance(budget_max, int) and budget_min >= budget_max:
            fields['budget'] = 'budgetMax must be greater than budgetMin'
        if not apply_by:
            fields['applyBy'] = 'applyBy date is required'

        if fields:
            return Response({
                'error': {'code': 'validation_error', 'message': next(iter(fields.values()))},
                'message': next(iter(fields.values())),
                'code': 'validation_error',
                'fields': fields,
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        profile = Profile.objects.filter(id=request.user.id).first()
        campaign = Campaign.objects.create(
            id=uuid.uuid4(),
            brand=profile,
            title=title,
            platform=platform,
            deliverables=deliverables,
            budget_min=budget_min,
            budget_max=budget_max,
            apply_by=apply_by,
            brief=brief or None,
            status=camp_status,
            created_at=django_tz.now(),
            updated_at=django_tz.now(),
        )

        return Response({
            'id': str(campaign.id),
            'title': campaign.title,
            'status': campaign.status,
            'platform': campaign.platform,
            'deliverables': campaign.deliverables,
            'budgetMin': campaign.budget_min,
            'budgetMax': campaign.budget_max,
            'applyBy': campaign.apply_by,
            'brief': campaign.brief,
            'createdAt': campaign.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

    def get(self, request):
        campaigns = Campaign.objects.filter(brand_id=request.user.id, deleted_at__isnull=True).order_by('-created_at')
        res = []
        for camp in campaigns:
            bids = CampaignBid.objects.filter(campaign_id=camp.id).select_related('creator')
            avatars = [b.creator.image for b in bids if b.creator and b.creator.image][:5]
            res.append({
                'id': str(camp.id),
                'title': camp.title,
                'status': camp.status,
                'platform': camp.platform,
                'deliverables': camp.deliverables,
                'budgetMin': camp.budget_min,
                'budgetMax': camp.budget_max,
                'applyBy': camp.apply_by,
                'bidCount': bids.count(),
                'proposalAvatars': avatars,
                'createdAt': camp.created_at.isoformat(),
            })
        return Response(res)

class CampaignDetailView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
        camp = Campaign.objects.filter(id=pk, deleted_at__isnull=True).first()
        if not camp or (str(camp.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'id': str(camp.id),
            'title': camp.title,
            'status': camp.status,
            'platform': camp.platform,
            'deliverables': camp.deliverables,
            'budgetMin': camp.budget_min,
            'budgetMax': camp.budget_max,
            'applyBy': camp.apply_by,
            'brief': camp.brief,
            'createdAt': camp.created_at.isoformat(),
        })

    def patch(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
        camp = Campaign.objects.filter(id=pk, deleted_at__isnull=True).first()
        if not camp or (str(camp.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        if camp.status in ['closed', 'awarded', 'cancelled']:
            return Response({'error': {'code': 'conflict', 'message': f"Campaigns with status '{camp.status}' cannot be edited"}}, status=status.HTTP_409_CONFLICT)

        body = request.data or {}
        allowed_fields = {'title', 'platform', 'deliverables', 'budgetMin', 'budgetMax', 'applyBy', 'brief'}
        unknown_fields = [k for k in body.keys() if k not in allowed_fields]
        if unknown_fields:
            return Response({'error': {'code': 'unprocessable_entity', 'message': f"Unknown fields: {', '.join(unknown_fields)}"}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        has_bids = CampaignBid.objects.filter(campaign_id=pk).exists()
        if has_bids:
            locked_attempted = [k for k in ['budgetMin', 'budgetMax', 'platform', 'deliverables', 'applyBy'] if k in body]
            if locked_attempted:
                return Response({'error': {'code': 'conflict', 'message': 'Campaign has bids; budgetMin, budgetMax, deliverables, and applyBy are locked'}}, status=status.HTTP_409_CONFLICT)

        if 'applyBy' in body:
            try:
                apply_dt = datetime.fromisoformat(body['applyBy'])
                if apply_dt < datetime.now():
                    return Response({'error': {'code': 'unprocessable_entity', 'message': 'applyBy date cannot be in the past'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            except Exception:
                return Response({'error': {'code': 'unprocessable_entity', 'message': 'Invalid date for applyBy'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        new_min = body.get('budgetMin', camp.budget_min)
        new_max = body.get('budgetMax', camp.budget_max)
        if new_min is not None and new_max is not None and new_min >= new_max:
            return Response({'error': {'code': 'unprocessable_entity', 'message': 'budgetMin must be less than budgetMax'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if 'title' in body:
            camp.title = body['title']
        if 'platform' in body:
            camp.platform = body['platform']
        if 'deliverables' in body:
            camp.deliverables = body['deliverables']
        if 'budgetMin' in body:
            camp.budget_min = body['budgetMin']
        if 'budgetMax' in body:
            camp.budget_max = body['budgetMax']
        if 'applyBy' in body:
            camp.apply_by = body['applyBy']
        if 'brief' in body:
            camp.brief = body['brief']
        camp.updated_at = django_tz.now()
        camp.save()

        return Response({
            'id': str(camp.id),
            'title': camp.title,
            'status': camp.status,
            'platform': camp.platform,
            'deliverables': camp.deliverables,
            'budgetMin': camp.budget_min,
            'budgetMax': camp.budget_max,
            'applyBy': camp.apply_by,
            'brief': camp.brief,
            'createdAt': camp.created_at.isoformat(),
        })

    def delete(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
        camp = Campaign.objects.filter(id=pk, deleted_at__isnull=True).first()
        if not camp or (str(camp.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        if camp.status != 'draft':
            bid_count = CampaignBid.objects.filter(campaign_id=pk).count()
            order_count = Order.objects.filter(campaign_id=pk).count()
            if bid_count > 0 or order_count > 0:
                return Response({'error': {'code': 'conflict', 'message': 'Campaign has existing bids or orders and cannot be deleted'}}, status=status.HTTP_409_CONFLICT)

        camp.deleted_at = django_tz.now()
        camp.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class CampaignBidsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsBrandUser()]
        elif self.request.method == 'POST':
            return [IsCreatorUser()]
        return [IsBrandUser()]

    def get(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
        camp = Campaign.objects.filter(id=pk, deleted_at__isnull=True).first()
        if not camp or (str(camp.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        bids = CampaignBid.objects.filter(campaign_id=pk).select_related('creator').order_by('-created_at')
        res = [{
            'id': str(b.id),
            'creator': {
                'id': str(b.creator.id) if b.creator else None,
                'name': b.creator.name if b.creator else '',
                'note': b.note or '',
                'avatar': b.creator.image if b.creator else '',
            },
            'price': b.price,
            'status': b.status,
        } for b in bids]
        return Response(res)

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        # 1. Enforce creator status must be active
        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile or profile.status != 'active':
            return Response({'error': {'code': 'creator_not_active', 'message': 'Creator account must be active to submit bids'}}, status=status.HTTP_403_FORBIDDEN)

        # 2. Campaign must exist and not be soft deleted
        camp = Campaign.objects.filter(id=pk, deleted_at__isnull=True).first()
        if not camp:
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        # 3. Campaign status must be open_for_bids
        if camp.status != 'open_for_bids':
            return Response({'error': {'code': 'conflict', 'message': f'Campaign is not open for bids (status: {camp.status})'}}, status=status.HTTP_409_CONFLICT)

        # 4. applyBy must be in the future (fail closed if unparseable)
        if camp.apply_by:
            try:
                apply_str = camp.apply_by.replace('Z', '+00:00')
                apply_dt = datetime.fromisoformat(apply_str)
                if django_tz.is_naive(apply_dt):
                    apply_dt = django_tz.make_aware(apply_dt, timezone.utc)
                if apply_dt <= django_tz.now():
                    return Response({'error': {'code': 'conflict', 'message': 'Campaign applyBy deadline has passed'}}, status=status.HTTP_409_CONFLICT)
            except Exception:
                return Response({'error': {'code': 'conflict', 'message': 'Campaign deadline is invalid or cannot be verified'}}, status=status.HTTP_409_CONFLICT)

        body = request.data or {}
        price = body.get('price')
        note = body.get('note', '')

        # 5. Price an integer >= 1
        if not isinstance(price, int) or isinstance(price, bool) or price < 1:
            return Response({'error': {'code': 'validation_error', 'message': 'Price must be an integer >= 1'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # 6. Price within budget_min and budget_max
        if (camp.budget_min is not None and price < camp.budget_min) or (camp.budget_max is not None and price > camp.budget_max):
            return Response({'error': {'code': 'validation_error', 'message': f'Price must be between {camp.budget_min} and {camp.budget_max}'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # 7. Creator identity strictly from authenticated user (no auto-creation with invented stats)
        creator = Creator.objects.filter(id=str(request.user.id)).first()
        if not creator:
            cp = CreatorProfile.objects.filter(user_id=request.user.id).first()
            if cp and cp.slug:
                creator = Creator.objects.filter(id=cp.slug).first()
        if not creator:
            return Response({'error': {'code': 'creator_not_listed', 'message': 'Creator profile is not listed in catalog'}}, status=status.HTTP_403_FORBIDDEN)

        if creator.status != 'active':
            return Response({'error': {'code': 'creator_not_active', 'message': 'Creator listing is not active'}}, status=status.HTTP_403_FORBIDDEN)

        # 8. One bid per creator per campaign (unique check plus DB unique index)
        if CampaignBid.objects.filter(campaign_id=pk, creator=creator).exists():
            return Response({'error': {'code': 'conflict', 'message': 'Creator has already submitted a bid for this campaign'}}, status=status.HTTP_409_CONFLICT)

        try:
            bid = CampaignBid.objects.create(
                id=uuid.uuid4(),
                campaign=camp,
                creator=creator,
                price=price,
                note=note or None,
                status='submitted',
                created_at=django_tz.now(),
                updated_at=django_tz.now(),
            )
        except IntegrityError:
            return Response({'error': {'code': 'conflict', 'message': 'Creator has already submitted a bid for this campaign'}}, status=status.HTTP_409_CONFLICT)

        return Response({
            'id': str(bid.id),
            'campaignId': str(camp.id),
            'creatorId': str(creator.id),
            'price': bid.price,
            'note': bid.note,
            'status': bid.status,
            'createdAt': bid.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

class CampaignBidSelectView(APIView):
    permission_classes = [IsBrandUser]

    @transaction.atomic
    def post(self, request, pk, bid_id):
        if not is_valid_uuid(pk) or not is_valid_uuid(bid_id):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT id, brand_id, creator_id, campaign_id, bid_id, deliverable, amount, status, created_at FROM public.select_bid(%s::uuid, %s::uuid, %s::uuid);",
                    [pk, bid_id, request.user.id]
                )
                row = cursor.fetchone()
                if not row:
                    return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
                order_id, b_id, c_id, camp_id, s_bid_id, deliverable, amount, order_status, created_at = row
                return Response({
                    'order': {
                        'id': str(order_id),
                        'brandId': str(b_id),
                        'creatorId': str(c_id),
                        'campaignId': str(camp_id),
                        'bidId': str(s_bid_id),
                        'deliverable': deliverable,
                        'amount': amount,
                        'status': order_status,
                        'createdAt': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
                    },
                    'campaignId': str(camp_id),
                    'selectedBidId': str(s_bid_id),
                }, status=status.HTTP_201_CREATED)
            except DatabaseError as e:
                err_msg = str(e)
                if 'P0002' in err_msg or ('not found' in err_msg.lower() and 'bid' not in err_msg.lower()):
                    return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
                if 'P0003' in err_msg or 'Unauthorized' in err_msg:
                    return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)
                if 'P0005' in err_msg:
                    return Response({'error': {'code': 'bid_not_found', 'message': 'Bid not found'}}, status=status.HTTP_404_NOT_FOUND)
                if 'P0004' in err_msg or 'P0006' in err_msg or 'conflict' in err_msg.lower() or 'status' in err_msg.lower() or 'eligible' in err_msg.lower():
                    return Response({'error': {'code': 'conflict', 'message': err_msg.split('\n')[0].replace('CONTEXT:', '').strip()}}, status=status.HTTP_409_CONFLICT)
                return Response({'error': {'code': 'conflict', 'message': err_msg.split('\n')[0].strip()}}, status=status.HTTP_409_CONFLICT)
