import uuid
from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ..models import Order, OrderMessage, Creator, CreatorPackage, Profile
from ..permissions import IsBrandUser, IsActiveCreator, IsMarketplaceParticipant, is_valid_admin
from ..services import is_valid_uuid

from .marketplace_views import format_creator_card

def format_order(o):
    creator_card = format_creator_card(o.creator) if o.creator else {'id': str(o.creator_id)}
    return {
        'id': str(o.id),
        'creator': creator_card,
        'deliverable': o.deliverable,
        'amount': o.amount,
        'status': o.status,
        'campaignId': str(o.campaign_id) if o.campaign_id else None,
        'bidId': str(o.bid_id) if o.bid_id else None,
        'packageId': str(o.package_id) if o.package_id else None,
        'paymentIntent': o.payment_intent or None,
        'clientSecret': o.client_secret or None,
        'changeNote': o.change_note or None,
        'draftUrl': o.draft_url or None,
        'revisionCount': o.revision_count or 0,
        'fundedAt': o.funded_at.isoformat() if o.funded_at else None,
        'releasedAt': o.released_at.isoformat() if o.released_at else None,
        'createdAt': o.created_at.isoformat() if o.created_at else None,
        'updatedAt': o.updated_at.isoformat() if o.updated_at else None,
    }

class OrderListCreateView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        orders = Order.objects.filter(brand_id=request.user.id).select_related('creator').order_by('-created_at')
        return Response([format_order(o) for o in orders])

    def post(self, request):
        body = request.data or {}
        creator_id = body.get('creatorId')
        amount = body.get('amount')
        deliverable = body.get('deliverable', 'Custom Deliverable')
        package_id = body.get('packageId')
        campaign_id = body.get('campaignId')
        bid_id = body.get('bidId')

        if not creator_id:
            return Response({'error': {'code': 'missing_creator', 'message': 'creatorId is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not isinstance(amount, (int, float)) or amount <= 0:
            return Response({'error': {'code': 'invalid_amount', 'message': 'Valid positive amount in INR is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        creator = Creator.objects.filter(id=creator_id).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'creator_not_found', 'message': 'Creator not found'}}, status=status.HTTP_404_NOT_FOUND)

        package = CreatorPackage.objects.filter(id=package_id).first() if package_id else None
        profile = Profile.objects.filter(id=request.user.id).first()

        now = django_tz.now()
        order = Order.objects.create(
            id=uuid.uuid4(),
            brand=profile,
            creator=creator,
            package=package,
            deliverable=deliverable,
            amount=int(amount),
            status='awaiting_payment',
            revision_count=0,
            created_at=now,
            updated_at=now,
        )

        return Response(format_order(order), status=status.HTTP_201_CREATED)

class OrderDetailView(APIView):
    permission_classes = [IsMarketplaceParticipant]

    def get(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)
        order = Order.objects.filter(id=pk).select_related('creator').first()
        if not order:
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)
        if (
            str(order.brand_id) != str(request.user.id)
            and str(order.creator_id) != str(request.user.id)
            and not is_valid_admin(request.user)
        ):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        return Response(format_order(order))


class OrderPayView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=pk).select_related('creator').first()
            if not order or (str(order.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
                return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

            if order.status != 'awaiting_payment':
                return Response({'error': {'code': 'invalid_order_state', 'message': f"Payment is allowed only from awaiting_payment, current status: {order.status}"}}, status=status.HTTP_409_CONFLICT)

            clean_id = str(order.id).replace('-', '')[:16]
            payment_intent = f"pi_test_{clean_id}"
            client_secret = f"pi_test_secret_{clean_id}"

            order.payment_intent = payment_intent
            order.client_secret = client_secret
            order.updated_at = django_tz.now()
            order.save()

            return Response({
                'orderId': str(order.id),
                'amount': order.amount,
                'currency': 'INR',
                'clientToken': client_secret,
                'clientSecret': client_secret,
                'paymentIntent': payment_intent,
                'status': 'awaiting_payment',
                'provider': 'razorpay_test',
            })

class OrderConfirmStubView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=pk).select_related('creator').first()
            if not order or (str(order.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
                return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

            if order.status != 'awaiting_payment':
                return Response({'error': {'code': 'invalid_order_state', 'message': f"Order cannot be confirmed from status: {order.status}"}}, status=status.HTTP_409_CONFLICT)

            now = django_tz.now()
            order.status = 'in_escrow'
            order.funded_at = now
            order.updated_at = now
            order.save()

            return Response(format_order(order))

class OrderSubmitDraftView(APIView):
    permission_classes = [IsActiveCreator]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=pk).select_related('creator').first()
            if not order:
                return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

            if str(order.creator_id) != str(request.user.id) and not is_valid_admin(request.user):
                return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)


            if order.status not in ['in_escrow', 'changes_requested']:
                return Response({'error': {'code': 'invalid_order_state', 'message': f"Draft submission allowed only from in_escrow or changes_requested, current: {order.status}"}}, status=status.HTTP_409_CONFLICT)

            body = request.data or {}
            draft_url = body.get('draftUrl') or body.get('url') or 'https://assets.collivra.com/drafts/demo-reel.mp4'
            note = body.get('note') or 'Draft video submitted for review.'

            now = django_tz.now()
            order.draft_url = draft_url
            order.status = 'draft_submitted'
            order.updated_at = now
            order.save()

            # Add message in thread
            sender_profile = Profile.objects.filter(id=request.user.id).first()
            OrderMessage.objects.create(
                id=uuid.uuid4(),
                order=order,
                sender=sender_profile,
                sender_name=sender_profile.name if sender_profile else 'Admin / Creator',
                sender_role='creator',
                message=note,
                attachments=[{'url': draft_url, 'type': 'video'}],
                created_at=now,
            )

            return Response(format_order(order))

class OrderRequestChangesView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        body = request.data or {}
        note = (body.get('note') or body.get('feedback') or body.get('comment') or '').strip()
        if not note:
            return Response({'error': {'code': 'missing_note', 'message': 'Change request note is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=pk).select_related('creator').first()
            if not order or (str(order.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
                return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

            if order.status != 'draft_submitted':
                return Response({
                    'error': {'code': 'invalid_order_state', 'message': f"Changes can only be requested from draft_submitted, current: {order.status}"},
                    'code': 'invalid_order_state',
                    'message': f"Changes can only be requested from draft_submitted, current: {order.status}",
                }, status=status.HTTP_409_CONFLICT)

            current_rev = order.revision_count or 0
            if current_rev >= 2:
                return Response({
                    'error': {'code': 'max_revisions_reached', 'message': 'Maximum 2 revisions allowed for this order'},
                    'code': 'max_revisions_reached',
                    'message': 'Maximum 2 revisions allowed for this order',
                }, status=status.HTTP_409_CONFLICT)

            now = django_tz.now()
            order.revision_count = current_rev + 1
            order.change_note = note
            order.status = 'changes_requested'
            order.updated_at = now
            order.save()

            sender_profile = Profile.objects.filter(id=request.user.id).first()
            OrderMessage.objects.create(
                id=uuid.uuid4(),
                order=order,
                sender=sender_profile,
                sender_name=sender_profile.company_name or sender_profile.name if sender_profile else 'Brand',
                sender_role='brand',
                message=f"Changes requested: {note}",
                attachments=[],
                created_at=now,
            )

            return Response(format_order(order))

class OrderApproveView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=pk).select_related('creator').first()
            if not order or (str(order.brand_id) != str(request.user.id) and getattr(request.user, 'role', '') != 'admin'):
                return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

            # Idempotent 200 if already released
            if order.status == 'released':
                return Response(format_order(order))

            if order.status != 'draft_submitted':
                return Response({'error': {'code': 'invalid_order_state', 'message': f"Order can only be approved from draft_submitted, current: {order.status}"}}, status=status.HTTP_409_CONFLICT)

            now = django_tz.now()
            order.status = 'released'
            order.released_at = now
            order.updated_at = now
            order.save()

            sender_profile = Profile.objects.filter(id=request.user.id).first()
            OrderMessage.objects.create(
                id=uuid.uuid4(),
                order=order,
                sender=sender_profile,
                sender_name=sender_profile.company_name or sender_profile.name if sender_profile else 'Brand',
                sender_role='brand',
                message='Deliverable approved! Escrow payment has been released to the creator.',
                attachments=[],
                created_at=now,
            )

            return Response(format_order(order))

class OrderMessagesView(APIView):
    permission_classes = [IsMarketplaceParticipant]

    def get(self, request, pk):
        order = Order.objects.filter(id=pk).first()
        if not order:
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)
        if (
            str(order.brand_id) != str(request.user.id)
            and str(order.creator_id) != str(request.user.id)
            and not is_valid_admin(request.user)
        ):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        messages = OrderMessage.objects.filter(order_id=pk).order_by('created_at')
        res = [{
            'id': str(m.id),
            'orderId': str(m.order_id),
            'senderId': str(m.sender_id) if m.sender_id else None,
            'senderName': m.sender_name,
            'senderRole': m.sender_role,
            'message': m.message,
            'attachments': m.attachments or [],
            'createdAt': m.created_at.isoformat(),
        } for m in messages]
        return Response(res)

    def post(self, request, pk):
        order = Order.objects.filter(id=pk).first()
        if not order:
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)
        if (
            str(order.brand_id) != str(request.user.id)
            and str(order.creator_id) != str(request.user.id)
            and not is_valid_admin(request.user)
        ):
            return Response({'error': {'code': 'order_not_found', 'message': 'Order not found'}}, status=status.HTTP_404_NOT_FOUND)

        body = request.data or {}
        message_text = (body.get('message') or '').strip()
        if not message_text:
            return Response({'error': {'code': 'missing_message', 'message': 'Message is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        profile = Profile.objects.filter(id=request.user.id).first()
        now = django_tz.now()
        sender_role = 'creator' if getattr(request.user, 'role', '') == 'creator' else 'brand'
        sender_name = profile.name if (profile and sender_role == 'creator') else (profile.company_name or profile.name if profile else 'Brand')

        msg = OrderMessage.objects.create(
            id=uuid.uuid4(),
            order=order,
            sender=profile,
            sender_name=sender_name,
            sender_role=sender_role,
            message=message_text,
            attachments=body.get('attachments', []),
            created_at=now,
        )


        return Response({
            'id': str(msg.id),
            'orderId': str(msg.order_id),
            'senderId': str(msg.sender_id) if msg.sender_id else None,
            'senderName': msg.sender_name,
            'senderRole': msg.sender_role,
            'message': msg.message,
            'attachments': msg.attachments,
            'createdAt': msg.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)
