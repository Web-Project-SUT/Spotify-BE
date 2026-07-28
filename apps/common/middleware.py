from django.conf import settings


class MediaCorsMiddleware:
    """Stamps Access-Control-Allow-Origin on /media/ responses.

    django-cors-headers only covers views behind DRF/Django; static media
    served via MEDIA_URL bypasses it, which taints the <canvas> the FE uses
    to sample cover-art colour (Player.tsx crossOrigin="anonymous" read).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(f"/{settings.MEDIA_URL.strip('/')}/"):
            response["Access-Control-Allow-Origin"] = "*"
        return response
