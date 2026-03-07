from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    """Prevent new user registration via manual forms.

    Only Google OAuth can create accounts (handled by GoogleLoginAdapter).
    """

    def is_open_for_signup(self, request):
        return False


class GoogleLoginAdapter(DefaultSocialAccountAdapter):
    """Handle Google OAuth login: auto-create or link users by email."""

    def is_open_for_signup(self, request, sociallogin):
        # Allow signup only via Google OAuth
        return True

    def pre_social_login(self, request, sociallogin):
        """Link Google account to existing user if email matches."""
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return

        try:
            user = User.objects.get(email=email)
            if not sociallogin.is_existing:
                sociallogin.connect(request, user)
        except User.DoesNotExist:
            pass

    def populate_user(self, request, sociallogin, data):
        """Set user fields from Google profile data."""
        user = super().populate_user(request, sociallogin, data)
        user.role = User.Role.SALES
        return user

    def save_user(self, request, sociallogin, form=None):
        """Save new user created via Google OAuth."""
        user = super().save_user(request, sociallogin, form)
        user.set_unusable_password()
        user.save(update_fields=['password'])
        return user
