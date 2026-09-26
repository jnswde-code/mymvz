from django.contrib.auth import logout


class RequireSecondFactorMiddleware:
    """End every session that is logged in but not verified by a second factor.

    The login view only logs in after the code, so this should never fire.
    It covers what could go wrong elsewhere: a stray `login()` call, or a
    device removed with `reset_second_factor` while its session is open.
    Must come after `django_otp.middleware.OTPMiddleware`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_verified():
            logout(request)
        return self.get_response(request)
