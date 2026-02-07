from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from yaml import load as load_yaml, Loader
from requests import get
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter

@shared_task
def send_email_task(subject, message, from_email, recipient_list):
    """Асинхронная отправка email"""
    msg = EmailMultiAlternatives(subject, message, from_email, recipient_list)
    msg.send()
    return True

@shared_task
def import_products_task(url, user_id):
    """Асинхронный импорт товаров"""
    # Код из PartnerView.post()
    # ...
    return {"status": "success", "imported": count}