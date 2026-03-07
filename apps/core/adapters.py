from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    """Prevent new user registration via allauth forms."""

    def is_open_for_signup(self, request):
        return False


class GoogleOnlyLoginAdapter(DefaultSocialAccountAdapter):
    """Only allow Google login for users that already exist in the system."""

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        """Link Google account to existing user by email."""
        email = sociallogin.account.extra_data.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                if not sociallogin.is_existing:
                    sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass
