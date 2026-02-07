# Это позволит убедиться, что приложение Celery импортируется 
# при запуске Django, чтобы shared_task декоратор использовал это приложение
from __future__ import absolute_import, unicode_literals

from .celery import app as celery_app

__all__ = ('celery_app',)