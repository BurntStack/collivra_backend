def format_user_payload(profile, email=None):
    if not profile:
        return {}
    return {
        'id': str(profile.id),
        'name': profile.name,
        'email': email or profile.email,
        'companyName': profile.company_name,
        'role': profile.role,
        'isProfileCompleted': getattr(profile, 'is_profile_completed', False),
    }

