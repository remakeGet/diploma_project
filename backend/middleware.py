# backend/middleware.py

from backend.hawk_setup import get_hawk

class HawkMiddleware:
    """Middleware для автоматического перехвата исключений и отправки в Hawk"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """Автоматически вызывается при возникновении исключения"""
        hawk = get_hawk()
        if hawk:
            try:
                hawk.send(
                    exception,
                    {
                        'url': request.build_absolute_uri(),
                        'method': request.method,
                        'path': request.path,
                    }
                )
                print(f"✓ Middleware sent error to Hawk: {exception.__class__.__name__}")
            except Exception as e:
                print(f"✗ Middleware failed to send: {e}")
        return None