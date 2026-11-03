from rest_framework import serializers
from ...models import BrandProfiles, Profile


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
        # Support both camelCase and snake_case incoming payloads
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
