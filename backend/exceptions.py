# backend/exceptions.py

from rest_framework.views import exception_handler
from django.conf import settings
import traceback
from backend.hawk_setup import get_hawk

def hawk_exception_handler(exc, context):
    # Получаем стандартный ответ от DRF
    response = exception_handler(exc, context)
    
    # Получаем hawk через нашу функцию
    hawk = get_hawk()
    
    # Отправляем ошибку в Hawk
    request = context.get('request')
    if request and hawk:
        try:
            # Собираем контекст
            hawk_context = {
                'url': request.build_absolute_uri(),
                'method': request.method,
                'path': request.path,
                'user_id': request.user.id if request.user.is_authenticated else None,
                'user_email': request.user.email if request.user.is_authenticated else None,
                'exception': {
                    'type': exc.__class__.__name__,
                    'message': str(exc),
                    'traceback': traceback.format_exc()
                }
            }
            
            # Отправляем в Hawk
            hawk.send(
                exc,
                hawk_context,
                {
                    'id': request.user.id if request.user.is_authenticated else None,
                    'email': request.user.email if request.user.is_authenticated else None
                }
            )
            
        except Exception:
            # Подавляем ошибки отправки в Hawk
            pass
    
    return response