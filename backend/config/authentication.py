from rest_framework.authentication import SessionAuthentication


class ConsumerSessionAuthentication(SessionAuthentication):
    """Consumer writes require CSRF even before Django user authentication."""
    def authenticate(self, request):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            self.enforce_csrf(request)
        return super().authenticate(request)
