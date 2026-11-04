import re
from datetime import date
from rest_framework import serializers
from ...models import BrandProfiles, CreatorProfiles, Profile


class BrandOnboardingSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    brand_name = serializers.CharField(max_length=255, required=True, error_messages={'required': 'Brand name is required.'})
    brand_logo = serializers.CharField(max_length=1024, required=False, allow_blank=True, allow_null=True)
    brand_website = serializers.CharField(max_length=1024, required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(max_length=100, default='India', required=False)
    region_state = serializers.CharField(max_length=150, required=True, error_messages={'required': 'State/Region is required.'})
    city = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    mobile = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)
    business_category = serializers.ChoiceField(
        choices=BrandProfiles.BUSINESS_CATEGORY_CHOICES,
        required=True,
        error_messages={'required': 'Business category is required.'}
    )
    geographical_scope = serializers.ChoiceField(
        choices=BrandProfiles.GEOGRAPHICAL_SCOPE_CHOICES,
        required=True,
        error_messages={'required': 'Geographical scope is required.'}
    )
    terms_accepted = serializers.BooleanField(required=True)

    class Meta:
        model = BrandProfiles
        fields = [
            'first_name',
            'last_name',
            'brand_name',
            'brand_logo',
            'brand_website',
            'country',
            'region_state',
            'city',
            'mobile',
            'business_category',
            'geographical_scope',
            'terms_accepted',
        ]

    def to_internal_value(self, data):
        normalized = {}
        key_map = {
            'firstName': 'first_name',
            'lastName': 'last_name',
            'brandName': 'brand_name',
            'brandLogo': 'brand_logo',
            'brandWebsite': 'brand_website',
            'regionState': 'region_state',
            'businessCategory': 'business_category',
            'geographicalScope': 'geographical_scope',
            'termsAccepted': 'terms_accepted',
        }
        for k, v in data.items():
            target_key = key_map.get(k, k)
            normalized[target_key] = v

        return super().to_internal_value(normalized)

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError('You must accept the terms and conditions to proceed.')
        return value

    def validate_brand_name(self, value):
        val = (value or '').strip()
        if not val or len(val) < 2:
            raise serializers.ValidationError('Brand name must be at least 2 characters long.')
        return val

    def validate_region_state(self, value):
        val = (value or '').strip()
        if not val:
            raise serializers.ValidationError('State or region is required.')
        return val

    def validate_brand_website(self, value):
        val = (value or '').strip()
        if not val:
            return ''
        if not val.startswith(('http://', 'https://')):
            val = f'https://{val}'
        return val

    def validate_mobile(self, value):
        val = (value or '').strip()
        if not val:
            return None
        from ...services import normalize_mobile
        norm = normalize_mobile(val)
        if not norm:
            raise serializers.ValidationError('Invalid mobile number. Please enter a valid 10-digit Indian mobile number.')
        return norm


class CreatorOnboardingSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    dob = serializers.DateField(required=True, error_messages={'required': 'Date of birth is required.'})
    gender = serializers.ChoiceField(
        choices=CreatorProfiles.GENDER_CHOICES,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    category = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    languages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    city = serializers.CharField(max_length=150, required=True, error_messages={'required': 'City is required.'})
    region_state = serializers.CharField(max_length=150, required=True, error_messages={'required': 'State or region is required.'})
    country = serializers.CharField(max_length=100, default='India', required=False)

    instagram_handle = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    youtube_handle = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    tiktok_handle = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    social_links = serializers.DictField(required=False, default=dict)

    pan_number = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = CreatorProfiles
        fields = [
            'first_name',
            'last_name',
            'dob',
            'gender',
            'category',
            'bio',
            'languages',
            'city',
            'region_state',
            'country',
            'instagram_handle',
            'youtube_handle',
            'tiktok_handle',
            'social_links',
            'pan_number',
        ]

    def to_internal_value(self, data):
        normalized = {}
        key_map = {
            'firstName': 'first_name',
            'lastName': 'last_name',
            'dateOfBirth': 'dob',
            'regionState': 'region_state',
            'instagramHandle': 'instagram_handle',
            'youtubeHandle': 'youtube_handle',
            'tiktokHandle': 'tiktok_handle',
            'socialLinks': 'social_links',
            'panNumber': 'pan_number',
        }
        for k, v in data.items():
            target_key = key_map.get(k, k)
            normalized[target_key] = v

        # If languages is passed as comma-separated string, convert to list
        if isinstance(normalized.get('languages'), str):
            normalized['languages'] = [l.strip() for l in normalized['languages'].split(',') if l.strip()]

        return super().to_internal_value(normalized)

    def validate_dob(self, value):
        today = date.today()
        if value > today:
            raise serializers.ValidationError('Date of birth cannot be in the future.')
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError('You must be at least 18 years old to register as a creator.')
        return value

    def validate_pan_number(self, value):
        val = (value or '').strip().upper()
        if not val:
            return None
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', val):
            raise serializers.ValidationError('Invalid PAN number format (expected 5 letters, 4 digits, 1 letter, e.g. ABCDE1234F).')
        return val

    def validate_instagram_handle(self, value):
        val = (value or '').strip()
        if val.startswith('@'):
            val = val[1:]
        return val or None

    def validate_youtube_handle(self, value):
        val = (value or '').strip()
        if val.startswith('@'):
            val = val[1:]
        return val or None

    def validate_tiktok_handle(self, value):
        val = (value or '').strip()
        if val.startswith('@'):
            val = val[1:]
        return val or None
