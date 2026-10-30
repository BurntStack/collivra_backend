from django.contrib import admin
from .models import (
    Profiles,
    Creators,
    CreatorPackages,
    CreatorReviews,
    CreatorProfiles,
    Campaigns,
    CampaignBids,
    Orders,
    OrderMessages,
    VerificationRequests,
    EmailVerificationOtp,
    AuditLog,
    CartItems,
    CustomOffers,
    Deliverables,
    Shortlists,
)


@admin.register(Profiles)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'role', 'status', 'company_name', 'created_at')
    list_filter = ('role', 'status', 'created_at')
    search_fields = ('name', 'email', 'company_name', 'mobile')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(Creators)
class CreatorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'platform', 'followers', 'rating', 'top_creator', 'status')
    list_filter = ('category', 'platform', 'top_creator', 'status')
    search_fields = ('name', 'category', 'location', 'platform')
    ordering = ('-rating',)


@admin.register(CreatorProfiles)
class CreatorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'city', 'slug', 'created_at')
    search_fields = ('user__name', 'user__email', 'category', 'city', 'slug')


@admin.register(CreatorPackages)
class CreatorPackageAdmin(admin.ModelAdmin):
    list_display = ('id', 'creator', 'title', 'price', 'platform', 'is_active')
    list_filter = ('platform', 'is_active')
    search_fields = ('title', 'creator__name')


@admin.register(CreatorReviews)
class CreatorReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'creator', 'name', 'stars', 'date')
    list_filter = ('stars',)
    search_fields = ('name', 'creator__name', 'text')


@admin.register(Campaigns)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'brand', 'platform', 'budget_min', 'budget_max', 'status', 'created_at')
    list_filter = ('platform', 'status', 'created_at')
    search_fields = ('title', 'brand__name', 'brand__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(CampaignBids)
class CampaignBidAdmin(admin.ModelAdmin):
    list_display = ('id', 'campaign', 'creator', 'price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('campaign__title', 'creator__name')


@admin.register(Orders)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'brand', 'creator', 'amount', 'status', 'revision_count', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'brand__name', 'brand__email', 'creator__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(OrderMessages)
class OrderMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'sender_name', 'sender_role', 'created_at')
    search_fields = ('sender_name', 'message')


@admin.register(VerificationRequests)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'status', 'submitted_at', 'reviewed_at')
    list_filter = ('type', 'status', 'submitted_at')
    search_fields = ('user__name', 'user__email')


@admin.register(EmailVerificationOtp)
class EmailVerificationOtpAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'role', 'expires_at', 'consumed_at', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('id', 'otp_hash', 'created_at')
    ordering = ('-created_at',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'entity', 'entity_id', 'actor_id', 'created_at')
    list_filter = ('action', 'entity', 'created_at')
    search_fields = ('action', 'entity', 'entity_id')
    readonly_fields = ('id', 'actor_id', 'action', 'entity', 'entity_id', 'details', 'created_at')
    ordering = ('-created_at',)


@admin.register(CartItems)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'creator', 'package', 'quantity', 'created_at')


@admin.register(CustomOffers)
class CustomOfferAdmin(admin.ModelAdmin):
    list_display = ('id', 'brand', 'creator', 'deliverable', 'budget', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Deliverables)
class DeliverableAdmin(admin.ModelAdmin):
    list_display = ('id', 'brand', 'creator', 'platform', 'status', 'created_at')
    list_filter = ('platform', 'status')


@admin.register(Shortlists)
class ShortlistAdmin(admin.ModelAdmin):
    list_display = ('id', 'brand', 'name', 'created_at')
    search_fields = ('name', 'brand__name')
