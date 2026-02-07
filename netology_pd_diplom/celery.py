import os
from celery import Celery

# Устанавливаем модуль настроек Django по умолчанию
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netology_pd_diplom.settings')

app = Celery('netology_pd_diplom')

# Загружаем настройки Celery из настроек Django с префиксом 'CELERY_'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим задачи во всех установленных приложениях Django
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Простая задача для отладки"""
    print(f'Request: {self.request!r}')