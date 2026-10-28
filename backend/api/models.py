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
    user = models.OneToOneField('Profiles', models.DB_CASCADE, primary_key=True)
    company_name = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'brand_profiles'


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


class CreatorProfiles(models.Model):
    user = models.OneToOneField('Profiles', models.DB_CASCADE, primary_key=True)
    category = models.TextField(blank=True, null=True)
    languages = ArrayField(models.TextField(), blank=True, default=list)
    city = models.TextField(blank=True, null=True)
    topics = ArrayField(models.TextField(), blank=True, default=list)
    headline = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    visibility = models.JSONField()
    slug = models.TextField(unique=True, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'creator_profiles'


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


class OtpSendLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    mobile = models.TextField()
    purpose = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'otp_send_log'


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
    failed_logins = models.IntegerField()
    locked_until = models.DateTimeField(blank=True, null=True)
    company_name = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'profiles'
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
