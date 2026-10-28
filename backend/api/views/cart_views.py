import uuid
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from ..models import CartItem, Creator, CreatorPackage, CustomOffer, Profile
from ..permissions import IsBrandUser
from ..services import is_valid_uuid
from .marketplace_views import format_creator_card

def get_full_cart(user_id):
    items_qs = CartItem.objects.filter(user_id=user_id).select_related('creator', 'package').order_by('created_at')
    items = []
    subtotal = 0
    for item in items_qs:
        creator = item.creator
        pkg = item.package
        price = pkg.price if pkg else 0
        line_total = price * item.quantity
        subtotal += line_total
        items.append({
            'id': str(item.id),
            'creator': format_creator_card(creator) if creator else None,
            'package': {
                'id': str(pkg.id),
                'title': pkg.title,
                'note': pkg.note,
                'price': pkg.price,
                'platform': pkg.platform,
            } if pkg else None,
            'quantity': item.quantity,
            'lineTotal': line_total,
        })
    return {'items': items, 'subtotal': subtotal}

class CartView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        cart = get_full_cart(request.user.id)
        return Response(cart)

class CartItemCreateView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request):
        body = request.data or {}
        creator_id = body.get('creatorId')
        package_id = body.get('packageId')
        quantity = body.get('quantity', 1)

        if not creator_id or not package_id:
            return Response({'error': {'code': 'validation_error', 'message': 'creatorId and packageId are required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not isinstance(quantity, int) or quantity < 1 or quantity > 20:
            return Response({'error': {'code': 'validation_error', 'message': 'Quantity must be between 1 and 20'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        pkg = CreatorPackage.objects.filter(id=package_id, creator_id=creator_id).select_related('creator').first()
        if not pkg:
            return Response({'error': {'code': 'package_not_found', 'message': 'Package not found for this creator'}}, status=status.HTTP_404_NOT_FOUND)

        if pkg.is_active is False:
            return Response({'error': {'code': 'package_inactive', 'message': 'Package is inactive'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if pkg.creator and pkg.creator.status != 'active':
            return Response({'error': {'code': 'creator_inactive', 'message': 'Creator is not active'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        existing = CartItem.objects.filter(user_id=request.user.id, creator_id=creator_id, package_id=package_id).first()
        if existing:
            new_qty = existing.quantity + quantity
            if new_qty > 20:
                return Response({'error': {'code': 'quantity_exceeded', 'message': 'Total item quantity cannot exceed 20'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            existing.quantity = new_qty
            existing.save()
        else:
            current_count = CartItem.objects.filter(user_id=request.user.id).count()
            if current_count >= 20:
                return Response({'error': {'code': 'cart_limit_exceeded', 'message': 'Cart cannot contain more than 20 lines'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            profile = Profile.objects.filter(id=request.user.id).first()
            CartItem.objects.create(
                id=uuid.uuid4(),
                user=profile,
                creator=pkg.creator,
                package=pkg,
                quantity=quantity,
                created_at=django_tz.now(),
                updated_at=django_tz.now(),
            )

        cart = get_full_cart(request.user.id)
        return Response(cart, status=status.HTTP_200_OK)

class CartItemDetailView(APIView):
    permission_classes = [IsBrandUser]

    def patch(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'item_not_found', 'message': 'Cart item not found'}}, status=status.HTTP_404_NOT_FOUND)
        item = CartItem.objects.filter(id=pk, user_id=request.user.id).first()
        if not item:
            return Response({'error': {'code': 'item_not_found', 'message': 'Cart item not found'}}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get('quantity')
        if not isinstance(quantity, int) or quantity < 1 or quantity > 20:
            return Response({'error': {'code': 'validation_error', 'message': 'Quantity must be between 1 and 20'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        item.quantity = quantity
        item.save()

        cart = get_full_cart(request.user.id)
        return Response(cart, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'item_not_found', 'message': 'Cart item not found'}}, status=status.HTTP_404_NOT_FOUND)
        item = CartItem.objects.filter(id=pk, user_id=request.user.id).first()
        if not item:
            return Response({'error': {'code': 'item_not_found', 'message': 'Cart item not found'}}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class OffersView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request):
        body = request.data or {}
        creator_id = body.get('creatorId')
        deliverable = (body.get('deliverable') or '').strip()
        budget = body.get('budget')
        message = (body.get('message') or '').strip()
        deadline = (body.get('deadline') or '').strip()

        if not creator_id or len(deliverable) < 3 or not isinstance(budget, int) or budget <= 0:
            return Response({'error': {'code': 'validation_error', 'message': 'Invalid offer parameters'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        creator = Creator.objects.filter(id=creator_id).first()
        if not creator:
            return Response({'error': {'code': 'creator_not_found', 'message': 'Creator not found'}}, status=status.HTTP_404_NOT_FOUND)

        profile = Profile.objects.filter(id=request.user.id).first()
        offer = CustomOffer.objects.create(
            id=uuid.uuid4(),
            brand=profile,
            creator=creator,
            deliverable=deliverable,
            budget=budget,
            message=message or None,
            deadline=deadline or None,
            status='pending',
            created_at=django_tz.now(),
            updated_at=django_tz.now(),
        )

        return Response({
            'id': str(offer.id),
            'creatorId': str(offer.creator_id),
            'deliverable': offer.deliverable,
            'budget': offer.budget,
            'message': offer.message,
            'deadline': offer.deadline,
            'status': offer.status,
            'createdAt': offer.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)
