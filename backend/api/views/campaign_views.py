import uuid
from datetime import datetime, timedelta
from django.db import transaction
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
        camp = Campaign.objects.filter(id=pk, deleted_at__isnull=True).first()
        if not camp:
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        if camp.status != 'open_for_bids':
            return Response({'error': {'code': 'conflict', 'message': 'Campaign is not open for bids'}}, status=status.HTTP_409_CONFLICT)

        body = request.data or {}
        price = body.get('price')
        note = body.get('note', '')

        if not isinstance(price, int) or price <= 0:
            return Response({'error': {'code': 'validation_error', 'message': 'Valid positive price required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        creator = Creator.objects.filter(id=str(request.user.id)).first()
        if not creator:
            cp = CreatorProfile.objects.filter(user_id=request.user.id).first()
            if cp and cp.slug:
                creator = Creator.objects.filter(id=cp.slug).first()
        if not creator:
            profile = Profile.objects.filter(id=request.user.id).first()
            creator_name = profile.name if (profile and profile.name) else 'Creator'
            creator = Creator.objects.create(
                id=str(request.user.id),
                name=creator_name,
                category='Lifestyle',
                location='India',
                city='Bengaluru',
                followers='10k',
                follower_count=10000,
                platform='Instagram',
                rating=5.0,
                review_count=0,
                price_from=price,
                deliverable=camp.deliverables or '1 Post',
                image='https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80',
                top_creator=False,
                replies_within='24 hours',
                is_seed=False,
                status='active',
                created_at=django_tz.now(),
                updated_at=django_tz.now(),
            )

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
        # 1. Lock campaign row for update
        camp = Campaign.objects.select_for_update().filter(id=pk, deleted_at__isnull=True).first()
        if not camp or (str(camp.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
            return Response({'error': {'code': 'campaign_not_found', 'message': 'Campaign not found'}}, status=status.HTTP_404_NOT_FOUND)

        # 2. Check campaign status
        if camp.status not in ['open_for_bids', 'closed']:
            return Response({'error': {'code': 'conflict', 'message': f"Campaign is not open for selection (status: {camp.status})"}}, status=status.HTTP_409_CONFLICT)

        # 3. Lock bid row for update
        bid = CampaignBid.objects.select_for_update().filter(id=bid_id, campaign_id=pk).first()
        if not bid:
            return Response({'error': {'code': 'bid_not_found', 'message': 'Bid not found'}}, status=status.HTTP_404_NOT_FOUND)

        if bid.status not in ['submitted', 'shortlisted']:
            return Response({'error': {'code': 'conflict', 'message': f"Bid is not eligible for selection (status: {bid.status})"}}, status=status.HTTP_409_CONFLICT)

        # 4. Create Order in awaiting_payment
        now = django_tz.now()
        order = Order.objects.create(
            id=uuid.uuid4(),
            brand=camp.brand,
            creator=bid.creator,
            campaign=camp,
            bid=bid,
            deliverable=camp.deliverables or 'Deliverables',
            amount=bid.price,
            status='awaiting_payment',
            revision_count=0,
            created_at=now,
            updated_at=now,
        )

        # 5. Update campaign status to awarded
        camp.status = 'awarded'
        camp.updated_at = now
        camp.save()

        # 6. Update winning bid to selected
        bid.status = 'selected'
        bid.updated_at = now
        bid.save()

        # 7. Update rival bids to rejected
        CampaignBid.objects.filter(campaign_id=pk, status__in=['submitted', 'shortlisted']).exclude(id=bid.id).update(status='rejected', updated_at=now)

        return Response({
            'order': {
                'id': str(order.id),
                'brandId': str(order.brand_id),
                'creatorId': str(order.creator_id),
                'campaignId': str(order.campaign_id),
                'bidId': str(order.bid_id),
                'deliverable': order.deliverable,
                'amount': order.amount,
                'status': order.status,
                'createdAt': order.created_at.isoformat(),
            },
            'campaignId': str(camp.id),
            'selectedBidId': str(bid.id),
        }, status=status.HTTP_201_CREATED)
