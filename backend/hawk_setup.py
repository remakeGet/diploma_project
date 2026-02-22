# backend/hawk_setup.py

from hawk_python_sdk import Hawk
from django.conf import settings

# Глобальный объект hawk
_hawk_instance = None

def get_hawk():
    """Возвращает глобальный экземпляр Hawk"""
    return _hawk_instance

def init_hawk(token, collector_endpoint='https://k1.hawk.so', release='1.0.0', before_send=None):
    """Инициализирует Hawk и сохраняет глобальный экземпляр"""
    global _hawk_instance
    _hawk_instance = Hawk({
        'token': token,
        'collector_endpoint': collector_endpoint,
        'release': release,
        'before_send': before_send,
    })
    return _hawk_instance

def hawk_before_send(event):
    """Очищаем чувствительные данные перед отправкой в Hawk"""
    if 'request' in event and 'data' in event['request']:
        if 'password' in event['request']['data']:
            event['request']['data']['password'] = '[FILTERED]'
        
        sensitive_fields = ['token', 'api_key', 'access_token', 'refresh_token']
        for field in sensitive_fields:
            if field in event['request']['data']:
                event['request']['data'][field] = '[FILTERED]'
    
    if 'request' in event and 'headers' in event['request']:
        headers = event['request']['headers']
        if 'Authorization' in headers:
            headers['Authorization'] = '[FILTERED]'
        if 'Cookie' in headers:
            headers['Cookie'] = '[FILTERED]'
    
    return event