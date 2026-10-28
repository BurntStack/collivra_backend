import math
from django.conf import settings
from django.db.models import Q
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ..models import Creator, CreatorPackage, CreatorReview, SavedCreator, Profile
from ..permissions import IsBrandUser

def format_creator_card(c):
    return {
        'id': c.id,
        'name': c.name,
        'category': c.category,
        'location': c.location,
        'followers': c.followers,
        'followerCount': c.follower_count,
        'platform': c.platform,
        'rating': float(c.rating) if c.rating is not None else 5.0,
        'reviewCount': c.review_count,
        'priceFrom': c.price_from,
        'deliverable': c.deliverable,
        'quotes': c.quotes if c.quotes is not None else [],
        'image': c.image,
        'topCreator': c.top_creator,
    }

class CreatorSuggestionsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([
            {'label': 'Trending on Instagram', 'query': {'platform': 'Instagram', 'sort': 'trending'}},
            {'label': 'Under ₹5,000', 'query': {'priceMax': 5000}},
            {'label': 'Top Tech Reviewers', 'query': {'category': 'Tech & Gadgets', 'sort': 'followers'}},
            {'label': 'Bengaluru Creators', 'query': {'city': 'Bengaluru'}},
            {'label': 'Fashion & Styling', 'query': {'category': 'Fashion & Styling'}},
            {'label': 'YouTube Reviews', 'query': {'platform': 'YouTube', 'sort': 'recommended'}},
        ])

class CreatorFiltersView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({
            'platforms': ['Instagram', 'YouTube', 'LinkedIn', 'X', 'Facebook'],
            'cities': ['Bengaluru', 'Mumbai', 'Delhi NCR', 'Hyderabad', 'Chennai', 'Pune', 'Kolkata'],
            'categories': [
                'Beauty, Skincare',
                'Fashion & Styling',
                'Tech & Gadgets',
                'Fitness & Health',
                'Food & Dining',
                'Finance & Business',
                'Travel & Lifestyle',
            ],
            'languages': ['English', 'Hindi', 'Kannada', 'Tamil', 'Telugu', 'Malayalam', 'Marathi'],
            'priceBuckets': [
                {'label': 'Under ₹5,000', 'max': 5000},
                {'label': '₹5,000 – ₹15,000', 'min': 5000, 'max': 15000},
                {'label': '₹15,000 – ₹30,000', 'min': 15000, 'max': 30000},
                {'label': '₹30,000+', 'min': 30000},
            ],
        })

class CreatorListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Creator.objects.all()

        show_seed = getattr(settings, 'SHOW_SEED_DATA', False)
        if not show_seed:
            qs = qs.filter(is_seed=False)

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(category__icontains=q) |
                Q(location__icontains=q) |
                Q(city__icontains=q)
            )

        platform = request.query_params.get('platform', '').strip()
        if platform:
            qs = qs.filter(platform__icontains=platform)

        category = request.query_params.get('category', '').strip()
        if category:
            qs = qs.filter(category__icontains=category)

        city = request.query_params.get('city', '').strip()
        if city:
            qs = qs.filter(city__icontains=city)

        price_min = request.query_params.get('priceMin')
        if price_min is not None and price_min.isdigit():
            qs = qs.filter(price_from__gte=int(price_min))

        price_max = request.query_params.get('priceMax')
        if price_max is not None and price_max.isdigit():
            qs = qs.filter(price_from__lte=int(price_max))

        followers_min = request.query_params.get('followersMin')
        if followers_min is not None and followers_min.isdigit():
            qs = qs.filter(follower_count__gte=int(followers_min))

        followers_max = request.query_params.get('followersMax')
        if followers_max is not None and followers_max.isdigit():
            qs = qs.filter(follower_count__lte=int(followers_max))

        gender = request.query_params.get('gender', '').strip()
        if gender:
            qs = qs.filter(gender__iexact=gender)

        language = request.query_params.get('language', '').strip()
        if language:
            qs = qs.filter(language__icontains=language)

        sort = request.query_params.get('sort', 'recommended')
        if sort == 'price_asc':
            qs = qs.order_by('price_from')
        elif sort == 'price_desc':
            qs = qs.order_by('-price_from')
        elif sort == 'followers':
            qs = qs.order_by('-follower_count')
        elif sort == 'trending':
            qs = qs.order_by('-top_creator', '-follower_count')
        else:
            qs = qs.order_by('-top_creator', '-rating', '-review_count')

        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, int(request.query_params.get('pageSize', 12)))

        total = qs.count()
        total_pages = math.ceil(total / page_size) if page_size else 1

        start = (page - 1) * page_size
        results = [format_creator_card(c) for c in qs[start:start + page_size]]

        return Response({
            'results': results,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': total_pages,
        })

class CreatorDetailView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        creator = Creator.objects.filter(id=pk).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'not_found', 'message': 'Creator not found'}, 'message': 'Creator not found'}, status=status.HTTP_404_NOT_FOUND)

        card = format_creator_card(creator)
        card.update({
            'bio': creator.bio,
            'gallery': creator.gallery or [],
            'badges': creator.badges or [],
            'repliesWithin': creator.replies_within or '2 hours',
        })
        return Response(card)

class CreatorPackagesView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        creator = Creator.objects.filter(id=pk).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'not_found', 'message': 'Creator not found'}, 'message': 'Creator not found'}, status=status.HTTP_404_NOT_FOUND)

        packages = CreatorPackage.objects.filter(creator_id=pk).order_by('price')
        res = [{
            'id': p.id,
            'title': p.title,
            'note': p.note,
            'price': p.price,
            'platform': p.platform,
        } for p in packages]
        return Response(res)

class CreatorReviewsView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        creator = Creator.objects.filter(id=pk).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'not_found', 'message': 'Creator not found'}, 'message': 'Creator not found'}, status=status.HTTP_404_NOT_FOUND)

        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, int(request.query_params.get('pageSize', 10)))

        qs = CreatorReview.objects.filter(creator_id=pk).order_by('-created_at')
        total = qs.count()
        total_pages = math.ceil(total / page_size) if page_size else 1

        start = (page - 1) * page_size
        reviews = [{
            'id': r.id,
            'name': r.name,
            'avatar': r.avatar,
            'stars': r.stars,
            'date': r.date,
            'text': r.text,
        } for r in qs[start:start + page_size]]

        return Response({
            'results': reviews,
            'rating': float(creator.rating) if creator and creator.rating is not None else 5.0,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': total_pages,
        })

class CreatorSimilarView(APIView):
    permission_classes = [IsBrandUser]

    def get(self, request, pk):
        current = Creator.objects.filter(id=pk).first()
        if not current or (current.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'not_found', 'message': 'Creator not found'}, 'message': 'Creator not found'}, status=status.HTTP_404_NOT_FOUND)

        show_seed = getattr(settings, 'SHOW_SEED_DATA', False)
        base_qs = Creator.objects.exclude(id=pk)
        if not show_seed:
            base_qs = base_qs.filter(is_seed=False)

        similar = []
        if current and current.category:
            primary = current.category.split(',')[0].strip()
            similar = list(base_qs.filter(category__icontains=primary).order_by('-rating')[:3])

        if not similar and current and current.platform:
            similar = list(base_qs.filter(platform__icontains=current.platform).order_by('-rating')[:3])

        if not similar:
            similar = list(base_qs.order_by('-rating')[:3])

        return Response([format_creator_card(c) for c in similar])

class CreatorSaveView(APIView):
    permission_classes = [IsBrandUser]

    def post(self, request, pk):
        user_id = request.user.id
        profile = Profile.objects.filter(id=user_id).first()
        creator = Creator.objects.filter(id=pk).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)) or not profile:
            return Response({'error': {'code': 'not_found', 'message': 'Not found'}}, status=status.HTTP_404_NOT_FOUND)

        SavedCreator.objects.update_or_create(
            user=profile,
            creator=creator,
            defaults={'saved_at': django_tz.now()}
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, pk):
        creator = Creator.objects.filter(id=pk).first()
        if not creator or (creator.is_seed and not getattr(settings, 'SHOW_SEED_DATA', False)):
            return Response({'error': {'code': 'not_found', 'message': 'Not found'}}, status=status.HTTP_404_NOT_FOUND)

        SavedCreator.objects.filter(user_id=request.user.id, creator_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
