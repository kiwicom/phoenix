import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount, SocialLogin, SocialToken
from allauth.utils import get_user_model
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """Disable open signup."""

    def is_open_for_signup(self, request):
        return False


class OpenSignupSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Enable open signup."""

    def is_open_for_signup(self, request, sociallogin):
        return True

    def is_auto_signup_allowed(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        """Check whether email is from correct domain.

        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).

        You can use this hook to intervene, e.g. abort the login by
        raising an ImmediateHttpResponse
        """
        if settings.ALLOWED_EMAIL_DOMAIN:
            domain = f"@{settings.ALLOWED_EMAIL_DOMAIN}"

            email = sociallogin.account.extra_data["email"]
            logger.info("Trying social sign up: %s", email)

            if not email.endswith(domain):
                msg = f"Email must be from {domain} domain!"
                logger.info(msg)
                messages.error(request, msg)
                raise ImmediateHttpResponse(redirect(settings.LOGIN_REDIRECT_URL))


def lookup(self):  # Ignore RadonBear
    """Monkey patch Socialogin lookup method."""
    assert not self.is_existing
    try:
        try:
            a = SocialAccount.objects.get(
                provider=self.account.provider, uid=self.account.uid
            )
        except:
            a = None

        if a is None:
            try:
                user = get_user_model().objects.get(email=self.user.email)
                a = SocialAccount.objects.create(
                    provider=self.account.provider, user=user, uid=self.account.uid
                )
            except:
                return
        # Update account
        a.extra_data = self.account.extra_data
        a.uid = self.account.uid
        self.account = a
        self.user = self.account.user
        a.save()
        # Update token
        if app_settings.STORE_TOKENS and self.token:
            assert not self.token.pk
            try:
                t = SocialToken.objects.get(account=self.account, app=self.token.app)
                t.token = self.token.token
                if self.token.token_secret:
                    # only update the refresh token if we got one
                    # many oauth2 providers do not resend the refresh token
                    t.token_secret = self.token.token_secret
                t.expires_at = self.token.expires_at
                t.save()
                self.token = t
            except SocialToken.DoesNotExist:
                self.token.account = a
                self.token.save()
    except SocialAccount.DoesNotExist:
        pass


SocialLogin.lookup = lookup
