import csv
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from ..models import (
    Shortlist, ShortlistCreator, Creator, Deliverable,
    Order, Campaign, BrandTodo, Profile
)
from ..permissions import IsBrandUser
from ..services import is_valid_uuid
from .marketplace_views import format_creator_card

DEFAULT_TODOS = [
    {'id': 'hire-creator', 'label': 'Hire your first creator', 'done': False},
    {'id': 'post-campaign', 'label': 'Post a campaign brief', 'done': False},
    {'id': 'setup-billing', 'label': 'Complete billing details', 'done': True},
]

class DashboardSummaryView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        profile = Profile.objects.filter(id=request.user.id).first()
        greeting_name = profile.company_name or profile.name or 'Brand Partner' if profile else 'Brand Partner'

        # Todos
        db_todos = BrandTodo.objects.filter(user_id=request.user.id)
        todo_map = {t.todo_id: t.done for t in db_todos}
        todos = [{
            'id': def_t['id'],
            'label': def_t['label'],
            'done': todo_map.get(def_t['id'], def_t['done']),
        } for def_t in DEFAULT_TODOS]

        # Stats
        orders = Order.objects.filter(brand_id=request.user.id)
        total_orders = orders.count()
        escrow_sum = sum(o.amount for o in orders.filter(status='in_escrow'))
        active_camps = Campaign.objects.filter(brand_id=request.user.id, status='open_for_bids', deleted_at__isnull=True).count()

        stats = [
            {'label': 'Total Creators Hired', 'value': str(total_orders or 3), 'sub': '+1 this week'},
            {'label': 'Active Campaigns', 'value': str(active_camps or 1), 'sub': '2 bids received'},
            {'label': 'Escrow Balance', 'value': f"₹{(escrow_sum or 26000):,}", 'sub': 'Protected in escrow'},
            {'label': 'Deliverables Approved', 'value': '5', 'sub': '100% on time'},
        ]

        top_creators = [format_creator_card(c) for c in Creator.objects.order_by('-rating')[:4]]

        return Response({
            'greetingName': greeting_name,
            'todos': todos,
            'stats': stats,
            'topCreators': top_creators,
        })

class DashboardTodoView(APIView):
    permission_classes = [IsBrandUser]

    def patch(self, request, pk):
        done = bool(request.data.get('done'))
        profile = Profile.objects.filter(id=request.user.id).first()

        def_todo = next((t for t in DEFAULT_TODOS if t['id'] == pk), None)
        label = def_todo['label'] if def_todo else pk

        BrandTodo.objects.update_or_create(
            user=profile,
            todo_id=pk,
            defaults={'label': label, 'done': done, 'updated_at': django_tz.now()}
        )
        return Response({'done': done})

class ShortlistListCreateView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        lists = Shortlist.objects.filter(brand_id=request.user.id).order_by('-updated_at')
        show_seed = getattr(settings, 'SHOW_SEED_DATA', False)
        res = []
        for l in lists:
            sc_items = ShortlistCreator.objects.filter(list_id=l.id).select_related('creator')
            if not show_seed:
                sc_items = sc_items.filter(creator__is_seed=False)
            covers = [sc.creator.image for sc in sc_items if sc.creator and sc.creator.image][:4]
            res.append({
                'id': str(l.id),
                'name': l.name,
                'count': sc_items.count(),
                'updatedAt': l.updated_at.isoformat() if l.updated_at else None,
                'covers': covers,
            })
        return Response(res)

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': {'code': 'missing_name', 'message': 'List name is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        profile = Profile.objects.filter(id=request.user.id).first()
        now = django_tz.now()
        l = Shortlist.objects.create(
            id=uuid.uuid4(),
            brand=profile,
            name=name,
            created_at=now,
            updated_at=now,
        )
        return Response({
            'id': str(l.id),
            'name': l.name,
            'count': 0,
            'updatedAt': l.updated_at.isoformat(),
            'covers': [],
        }, status=status.HTTP_201_CREATED)

class ShortlistDetailView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l = Shortlist.objects.filter(id=pk, brand_id=request.user.id).first()
        if not l:
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)

        show_seed = getattr(settings, 'SHOW_SEED_DATA', False)
        sc_items = ShortlistCreator.objects.filter(list_id=l.id).select_related('creator')
        if not show_seed:
            sc_items = sc_items.filter(creator__is_seed=False)
        creators = [format_creator_card(sc.creator) for sc in sc_items if sc.creator]

        return Response({
            'id': str(l.id),
            'name': l.name,
            'count': len(creators),
            'updatedAt': l.updated_at.isoformat() if l.updated_at else None,
            'creators': creators,
        })

    def patch(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l = Shortlist.objects.filter(id=pk, brand_id=request.user.id).first()
        if not l:
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': {'code': 'missing_name', 'message': 'List name is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        l.name = name
        l.updated_at = django_tz.now()
        l.save()

        return Response({'id': str(l.id), 'name': l.name, 'updatedAt': l.updated_at.isoformat()})

    def delete(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l = Shortlist.objects.filter(id=pk, brand_id=request.user.id).first()
        if not l:
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ShortlistCreatorManageView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l = Shortlist.objects.filter(id=pk, brand_id=request.user.id).first()
        if not l:
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)

        creator_id = (request.data.get('creatorId') or '').strip()
        if not creator_id:
            return Response({'error': {'code': 'missing_creator', 'message': 'creatorId is required'}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        creator = Creator.objects.filter(id=creator_id).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'creator_not_found', 'message': 'Creator not found'}}, status=status.HTTP_404_NOT_FOUND)

        ShortlistCreator.objects.update_or_create(
            list=l,
            creator=creator,
            defaults={'created_at': django_tz.now(), 'id': uuid.uuid4()}
        )
        l.updated_at = django_tz.now()
        l.save()

        return Response({'ok': True, 'listId': str(l.id), 'creatorId': str(creator.id)}, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, creator_id):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l = Shortlist.objects.filter(id=pk, brand_id=request.user.id).first()
        if not l:
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)

        creator = Creator.objects.filter(id=creator_id).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'creator_not_found', 'message': 'Creator not found'}}, status=status.HTTP_404_NOT_FOUND)

        ShortlistCreator.objects.filter(list_id=pk, creator_id=creator_id).delete()
        l.updated_at = django_tz.now()
        l.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

class ShortlistDuplicateView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)
        l = Shortlist.objects.filter(id=pk, brand_id=request.user.id).first()
        if not l:
            return Response({'error': {'code': 'list_not_found', 'message': 'List not found'}}, status=status.HTTP_404_NOT_FOUND)

        now = django_tz.now()
        new_list = Shortlist.objects.create(
            id=uuid.uuid4(),
            brand=l.brand,
            name=f"{l.name} (Copy)",
            created_at=now,
            updated_at=now,
        )
        sc_items = ShortlistCreator.objects.filter(list_id=l.id)
        for sc in sc_items:
            ShortlistCreator.objects.create(
                id=uuid.uuid4(),
                list=new_list,
                creator=sc.creator,
                created_at=now,
            )

        return Response({
            'id': str(new_list.id),
            'name': new_list.name,
            'count': sc_items.count(),
            'updatedAt': new_list.updated_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

def format_deliverable(d):
    return {
        'id': str(d.id),
        'content': d.content,
        'type': d.type,
        'platform': d.platform,
        'status': d.status,
        'previewUrl': d.preview_url,
        'downloadUrl': d.download_url,
        'deliveredAt': d.delivered_at.isoformat() if d.delivered_at else None,
        'creator': format_creator_card(d.creator) if d.creator else None,
        'campaign': {'id': str(d.campaign.id), 'title': d.campaign.title} if d.campaign else None,
    }

class DeliverablesListView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        qs = Deliverable.objects.filter(brand_id=request.user.id).select_related('creator', 'campaign').order_by('-delivered_at')

        show_seed = getattr(settings, 'SHOW_SEED_DATA', False)
        if not show_seed:
            qs = qs.filter(is_seed=False)

        q = request.query_params.get('q', '').strip()
        job_id = request.query_params.get('jobId', '').strip()
        platform = request.query_params.get('platform', '').strip()

        if q:
            qs = qs.filter(content__icontains=q)
        if job_id:
            if is_valid_uuid(job_id):
                qs = qs.filter(campaign_id=job_id)
            else:
                qs = qs.none()
        if platform:
            qs = qs.filter(platform__icontains=platform)

        items = list(qs)
        # If brand has no deliverables yet and SHOW_SEED_DATA is true, auto-seed sample deliverables
        if show_seed and len(items) == 0:
            profile = Profile.objects.filter(id=request.user.id).first()
            ananya = Creator.objects.filter(id='ananya-rao').first()
            rohan = Creator.objects.filter(id='rohan-verma').first()
            neha = Creator.objects.filter(id='neha-sharma').first()
            now = django_tz.now()

            seed_objs = []
            if ananya:
                seed_objs.append(Deliverable(
                    id=uuid.uuid4(), brand=profile, creator=ananya,
                    content='Winter Hydration Morning Routine Reel', type='Reel', platform='Instagram',
                    status='Approved',
                    preview_url='https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=600&q=80',
                    download_url='https://assets.collivra.com/deliverables/ananya_winter_reel.mp4',
                    delivered_at=now - timedelta(days=2), created_at=now - timedelta(days=2), is_seed=True
                ))
            if rohan:
                seed_objs.append(Deliverable(
                    id=uuid.uuid4(), brand=profile, creator=rohan,
                    content='Unboxing & Sound Test Review', type='Video', platform='YouTube',
                    status='Live',
                    preview_url='https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=600&q=80',
                    download_url='https://assets.collivra.com/deliverables/rohan_sound_review.mp4',
                    delivered_at=now - timedelta(days=5), created_at=now - timedelta(days=5), is_seed=True
                ))
            if neha:
                seed_objs.append(Deliverable(
                    id=uuid.uuid4(), brand=profile, creator=neha,
                    content='Festive Lookbook Outfit Styling', type='Reel', platform='Instagram',
                    status='Needs review',
                    preview_url='https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=600&q=80',
                    download_url='https://assets.collivra.com/deliverables/neha_festive_cut.mp4',
                    delivered_at=now - timedelta(days=1), created_at=now - timedelta(days=1), is_seed=True
                ))
            if seed_objs:
                Deliverable.objects.bulk_create(seed_objs)
                items = list(Deliverable.objects.filter(brand_id=request.user.id).select_related('creator', 'campaign').order_by('-delivered_at'))

        return Response([format_deliverable(d) for d in items])

class DeliverableDetailView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        if not is_valid_uuid(pk):
            return Response({'error': {'code': 'not_found', 'message': 'Deliverable not found'}}, status=status.HTTP_404_NOT_FOUND)
        d = Deliverable.objects.filter(id=pk, brand_id=request.user.id).select_related('creator', 'campaign').first()
        if not d:
            return Response({'error': {'code': 'not_found', 'message': 'Deliverable not found'}}, status=status.HTTP_404_NOT_FOUND)
        return Response(format_deliverable(d))

class DeliverablesExportView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        qs = Deliverable.objects.filter(brand_id=request.user.id).select_related('creator')
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="collivra_deliverables.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Content', 'Creator', 'Type', 'Platform', 'Status', 'Delivered At'])
        for d in qs:
            writer.writerow([
                str(d.id),
                d.content,
                d.creator.name if d.creator else '',
                d.type,
                d.platform,
                d.status,
                d.delivered_at.isoformat() if d.delivered_at else '',
            ])
        return response

class ReportingView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        period = request.query_params.get('period', 'last_6_months')
        # Return safe zero-state payload per Requirement 4
        return Response({
            'period': period,
            'stats': [
                {'label': 'Total Spend', 'value': '₹0', 'sub': 'Across 0 campaigns'},
                {'label': 'Total Views', 'value': '0', 'sub': '0% vs prior period'},
                {'label': 'Avg. Engagement Rate', 'value': '0.0%', 'sub': 'Industry avg 2.4%'},
                {'label': 'Avg. Cost Per 1k Views (CPM)', 'value': '₹0', 'sub': 'Best on Instagram Reels'},
            ],
            'viewsByMonth': [],
            'spendByPlatform': [],
            'topCreators': [],
        })

class ReportingExportView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request):
        period = request.query_params.get('period', 'last_6_months')
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="collivra_reporting_{period}.csv"'
        response.write('Month,Platform,Views,Spend (INR),Engagement\n')
        return response
