# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.postgres.fields import ArrayField


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor_id = models.UUIDField(blank=True, null=True)
    action = models.TextField()
    entity = models.TextField()
    entity_id = models.TextField(blank=True, null=True)
    details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'audit_log'


class BrandProfiles(models.Model):
    BUSINESS_CATEGORY_CHOICES = [
        ('Fashion & Style', 'Fashion & Style'),
        ('Beauty & Personal Care', 'Beauty & Personal Care'),
        ('Health & Fitness', 'Health & Fitness'),
        ('Food & Culinary', 'Food & Culinary'),
        ('Home & Real Estate', 'Home & Real Estate'),
        ('Travel & Adventure', 'Travel & Adventure'),
    ]

    GEOGRAPHICAL_SCOPE_CHOICES = [
        ('Within City', 'Within City'),
        ('Within State', 'Within State'),
        ('Across Country', 'Across Country'),
        ('International', 'International'),
    ]

    user = models.OneToOneField('Profiles', models.DB_CASCADE, primary_key=True, related_name='brand_profile')
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    brand_name = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.TextField(blank=True, null=True)
    brand_logo = models.URLField(max_length=1024, blank=True, null=True)
    brand_website = models.URLField(max_length=1024, blank=True, null=True)
    country = models.CharField(max_length=100, default='India')
    region_state = models.CharField(max_length=150, blank=True, null=True)
    city = models.CharField(max_length=150, blank=True, null=True)
    mobile = models.CharField(max_length=32, blank=True, null=True)
    business_category = models.CharField(max_length=100, choices=BUSINESS_CATEGORY_CHOICES, blank=True, null=True)
    geographical_scope = models.CharField(max_length=100, choices=GEOGRAPHICAL_SCOPE_CHOICES, blank=True, null=True)
    terms_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'brand_profiles'
        verbose_name = 'Brand Profile'
        verbose_name_plural = 'Brand Profiles'


class BrandTodos(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'todo_id')
    user = models.ForeignKey('Profiles', models.DB_CASCADE)
    todo_id = models.TextField()
    label = models.TextField()
    done = models.BooleanField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'brand_todos'


class CampaignBids(models.Model):
    id = models.UUIDField(primary_key=True)
    campaign = models.ForeignKey('Campaigns', models.DB_CASCADE)
    creator = models.ForeignKey('Creators', models.DB_CASCADE)
    price = models.IntegerField()
    note = models.TextField(blank=True, null=True)
    status = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'campaign_bids'
        verbose_name = 'Campaign Bid'
        verbose_name_plural = 'Campaign Bids'


class Campaigns(models.Model):
    id = models.UUIDField(primary_key=True)
    brand = models.ForeignKey('Profiles', models.DB_CASCADE)
    title = models.TextField()
    platform = models.TextField()
    deliverables = models.TextField()
    budget_min = models.IntegerField()
    budget_max = models.IntegerField()
    apply_by = models.TextField()
    brief = models.TextField(blank=True, null=True)
    status = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'campaigns'
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaigns'


class CartItems(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey('Profiles', models.DB_CASCADE)
    creator = models.ForeignKey('Creators', models.DB_CASCADE)
    package = models.ForeignKey('CreatorPackages', models.DB_CASCADE)
    quantity = models.IntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'cart_items'
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = (('user', 'creator', 'package'),)


class CreatorKyc(models.Model):
    user = models.OneToOneField('Profiles', models.DB_CASCADE, primary_key=True)
    pan_ciphertext = models.TextField(blank=True, null=True)
    pan_last4 = models.TextField(blank=True, null=True)
    name_on_pan = models.TextField(blank=True, null=True)
    pan_valid = models.BooleanField(blank=True, null=True)
    pan_name_match = models.BooleanField(blank=True, null=True)
    id_doc_type = models.TextField(blank=True, null=True)
    id_file_key = models.TextField(blank=True, null=True)
    id_status = models.TextField(default='none')

    bank_account_ciphertext = models.TextField(blank=True, null=True)
    bank_account_last4 = models.TextField(blank=True, null=True)
    bank_ifsc = models.TextField(blank=True, null=True)
    bank_holder_name = models.TextField(blank=True, null=True)
    upi_id = models.TextField(blank=True, null=True)
    bank_verified = models.BooleanField(blank=True, null=True)
    bank_name_match = models.BooleanField(blank=True, null=True)
    provider = models.TextField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'creator_kyc'


class CreatorPackages(models.Model):
    id = models.TextField(primary_key=True)
    creator = models.ForeignKey('Creators', models.DB_CASCADE)
    title = models.TextField()
    note = models.TextField(blank=True, null=True)
    price = models.IntegerField()
    platform = models.TextField()
    created_at = models.DateTimeField()
    is_active = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'creator_packages'
        verbose_name = 'Creator Package'
        verbose_name_plural = 'Creator Packages'


class CreatorProfiles(models.Model):
    GENDER_CHOICES = [
        ('Female', 'Female'),
        ('Male', 'Male'),
        ('Non-Binary', 'Non-Binary'),
        ('Prefer not to say', 'Prefer not to say'),
        ('Other', 'Other'),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    KYC_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField('Profiles', models.DB_CASCADE, primary_key=True, related_name='creator_profile')
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, blank=True, null=True)

    # Localization & Bio
    category = models.TextField(blank=True, null=True)
    languages = ArrayField(models.TextField(), blank=True, default=list)
    city = models.CharField(max_length=150, blank=True, null=True)
    region_state = models.CharField(max_length=150, blank=True, null=True)
    country = models.CharField(max_length=100, default='India')
    topics = ArrayField(models.TextField(), blank=True, default=list)
    headline = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # Social Handles & Links
    instagram_handle = models.CharField(max_length=150, blank=True, null=True)
    youtube_handle = models.CharField(max_length=150, blank=True, null=True)
    tiktok_handle = models.CharField(max_length=150, blank=True, null=True)
    social_links = models.JSONField(default=dict, blank=True)

    # KYC & Verification
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    kyc_status = models.CharField(max_length=32, choices=KYC_STATUS_CHOICES, default='verified')

    # Marketplace Status
    approval_status = models.CharField(max_length=32, choices=APPROVAL_STATUS_CHOICES, default='approved')
    visibility = models.JSONField(default=dict, blank=True)
    slug = models.TextField(unique=True, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'creator_profiles'
        verbose_name = 'Creator Profile'
        verbose_name_plural = 'Creator Profiles'


class CreatorReviews(models.Model):
    id = models.TextField(primary_key=True)
    creator = models.ForeignKey('Creators', models.DB_CASCADE)
    name = models.TextField()
    avatar = models.TextField(blank=True, null=True)
    stars = models.IntegerField()
    date = models.TextField()
    text = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'creator_reviews'
        verbose_name = 'Creator Review'
        verbose_name_plural = 'Creator Reviews'


class Creators(models.Model):
    id = models.TextField(primary_key=True)
    name = models.TextField()
    category = models.TextField()
    location = models.TextField()
    city = models.TextField()
    followers = models.TextField()
    follower_count = models.IntegerField()
    platform = models.TextField()
    rating = models.DecimalField(max_digits=3, decimal_places=2)
    review_count = models.IntegerField()
    price_from = models.IntegerField()
    deliverable = models.TextField()
    quotes = ArrayField(models.TextField(), blank=True, default=list)
    image = models.TextField()
    top_creator = models.BooleanField()
    bio = models.TextField(blank=True, null=True)
    gallery = ArrayField(models.TextField(), blank=True, default=list)
    badges = ArrayField(models.TextField(), blank=True, default=list)
    replies_within = models.TextField()
    gender = models.TextField(blank=True, null=True)
    language = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    is_seed = models.BooleanField()
    status = models.TextField()

    class Meta:
        managed = False
        db_table = 'creators'
        verbose_name = 'Marketplace Creator'
        verbose_name_plural = 'Marketplace Creators (Catalog)'


class CustomOffers(models.Model):
    id = models.UUIDField(primary_key=True)
    brand = models.ForeignKey('Profiles', models.DB_CASCADE)
    creator = models.ForeignKey(Creators, models.DB_CASCADE)
    deliverable = models.TextField()
    budget = models.IntegerField()
    message = models.TextField(blank=True, null=True)
    deadline = models.TextField(blank=True, null=True)
    status = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'custom_offers'
        verbose_name = 'Custom Offer'
        verbose_name_plural = 'Custom Offers'


class Deliverables(models.Model):
    id = models.UUIDField(primary_key=True)
    brand = models.ForeignKey('Profiles', models.DB_CASCADE)
    creator = models.ForeignKey(Creators, models.DB_CASCADE)
    campaign = models.ForeignKey(Campaigns, models.DB_SET_NULL, blank=True, null=True, related_name='campaign_deliverables')
    order = models.ForeignKey('Orders', models.DB_SET_NULL, blank=True, null=True)
    content = models.TextField()
    type = models.TextField()
    platform = models.TextField()
    status = models.TextField()
    preview_url = models.TextField()
    download_url = models.TextField()
    delivered_at = models.DateTimeField()
    created_at = models.DateTimeField()
    is_seed = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'deliverables'
        verbose_name = 'Deliverable'
        verbose_name_plural = 'Deliverables'


class OrderMessages(models.Model):
    id = models.UUIDField(primary_key=True)
    order = models.ForeignKey('Orders', models.DB_CASCADE)
    sender = models.ForeignKey('Profiles', models.DB_SET_NULL, blank=True, null=True)
    sender_name = models.TextField(blank=True, null=True)
    sender_role = models.TextField(blank=True, null=True)
    message = models.TextField()
    attachments = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'order_messages'
        verbose_name = 'Order Message'
        verbose_name_plural = 'Order Messages'


class Orders(models.Model):
    id = models.UUIDField(primary_key=True)
    brand = models.ForeignKey('Profiles', models.DB_CASCADE)
    creator = models.ForeignKey(Creators, models.DB_CASCADE)
    campaign = models.OneToOneField(Campaigns, models.DB_SET_NULL, blank=True, null=True)
    bid = models.OneToOneField(CampaignBids, models.DB_SET_NULL, blank=True, null=True)
    package = models.ForeignKey(CreatorPackages, models.DB_SET_NULL, blank=True, null=True)
    deliverable = models.TextField()
    amount = models.IntegerField()
    status = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    payment_intent = models.TextField(blank=True, null=True)
    client_secret = models.TextField(blank=True, null=True)
    change_note = models.TextField(blank=True, null=True)
    draft_url = models.TextField(blank=True, null=True)
    released_at = models.DateTimeField(blank=True, null=True)
    revision_count = models.IntegerField()
    funded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'


class OtpSendLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    mobile = models.TextField()
    purpose = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'otp_send_log'


class EmailVerificationOtp(models.Model):
    id = models.UUIDField(primary_key=True)
    email = models.TextField()
    otp_hash = models.TextField()
    role = models.TextField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'email_verification_otps'


class MobileVerificationOtp(models.Model):
    id = models.UUIDField(primary_key=True)
    mobile = models.TextField()
    otp_hash = models.TextField()
    purpose = models.TextField(default='login')
    role = models.TextField(default='creator')
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'mobile_verification_otps'


class Profiles(models.Model):
    id = models.UUIDField(primary_key=True)
    role = models.TextField()  # This field type is a guess.
    status = models.TextField()  # This field type is a guess.
    name = models.TextField(blank=True, null=True)
    mobile = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    language = models.TextField()
    terms_version = models.TextField(blank=True, null=True)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    mobile_verified_at = models.DateTimeField(blank=True, null=True)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    failed_logins = models.IntegerField()
    locked_until = models.DateTimeField(blank=True, null=True)
    company_name = models.TextField(blank=True, null=True)
    is_profile_completed = models.BooleanField(default=False)
    approval_status = models.CharField(max_length=32, default='approved')

    class Meta:
        managed = False
        db_table = 'profiles'
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
        unique_together = (('mobile', 'role'),)


class SavedCreators(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'creator_id')
    user = models.ForeignKey(Profiles, models.DB_CASCADE)
    creator = models.ForeignKey(Creators, models.DB_CASCADE)
    saved_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'saved_creators'


class Settings(models.Model):
    key = models.TextField(primary_key=True)
    value = models.JSONField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'settings'


class ShortlistCreators(models.Model):
    id = models.UUIDField(primary_key=True)
    list = models.ForeignKey('Shortlists', models.DB_CASCADE)
    creator = models.ForeignKey(Creators, models.DB_CASCADE)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'shortlist_creators'
        unique_together = (('list', 'creator'),)


class Shortlists(models.Model):
    id = models.UUIDField(primary_key=True)
    brand = models.ForeignKey(Profiles, models.DB_CASCADE)
    name = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'shortlists'
        verbose_name = 'Shortlist'
        verbose_name_plural = 'Shortlists'


class SocialAccounts(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(Profiles, models.DB_CASCADE)
    platform = models.TextField()  # This field type is a guess.
    handle = models.TextField()
    external_id = models.TextField(blank=True, null=True)
    followers = models.IntegerField(blank=True, null=True)
    avg_views = models.IntegerField(blank=True, null=True)
    engagement = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    audience = models.JSONField(blank=True, null=True)
    stats_source = models.TextField()  # This field type is a guess.
    stats_synced_at = models.DateTimeField(blank=True, null=True)
    token_ciphertext = models.TextField(blank=True, null=True)
    connected_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'social_accounts'
        unique_together = (('user', 'platform'), ('platform', 'external_id'),)


class Uploads(models.Model):
    id = models.UUIDField(primary_key=True)
    owner = models.ForeignKey(Profiles, models.DB_CASCADE)
    purpose = models.TextField()
    bucket = models.TextField()
    file_key = models.TextField(unique=True)
    content_type = models.TextField()
    size_bytes = models.BigIntegerField()
    status = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'uploads'


class VerificationRequests(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.OneToOneField(Profiles, models.DB_CASCADE)
    type = models.TextField()  # This field type is a guess.
    status = models.TextField()  # This field type is a guess.
    reasons = ArrayField(models.TextField(), blank=True, default=list)
    message = models.TextField(blank=True, null=True)
    reviewer = models.ForeignKey(Profiles, models.DO_NOTHING, related_name='verificationrequests_reviewer_set', blank=True, null=True)
    submitted_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'verification_requests'
        verbose_name = 'Verification Request'
        verbose_name_plural = 'Verification Requests'


# Convenience aliases
Profile = Profiles
Creator = Creators
CreatorPackage = CreatorPackages
CreatorReview = CreatorReviews
Campaign = Campaigns
CampaignBid = CampaignBids
Order = Orders
OrderMessage = OrderMessages
CartItem = CartItems
Deliverable = Deliverables
CustomOffer = CustomOffers
Shortlist = Shortlists
ShortlistCreator = ShortlistCreators
SavedCreator = SavedCreators
CreatorProfile = CreatorProfiles
SocialAccount = SocialAccounts
BrandProfile = BrandProfiles
BrandTodo = BrandTodos
OtpSendLogModel = OtpSendLog
Upload = Uploads
Setting = Settings
VerificationRequest = VerificationRequests
EmailVerificationOtpModel = EmailVerificationOtp
