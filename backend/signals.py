from typing import Type
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User, ProductImage
from backend.tasks import (
    send_email_task, 
    process_user_avatar, 
    process_product_image
)

new_user_registered = Signal()
new_order = Signal()

@receiver(post_save, sender=User)
def user_avatar_handler(sender, instance, created, **kwargs):
    """
    Запускаем обработку аватара после сохранения пользователя.
    """
    if instance.avatar:
        # Запускаем асинхронную обработку
        process_user_avatar.delay(instance.id)

@receiver(post_save, sender=ProductImage)
def product_image_handler(sender, instance, created, **kwargs):
    """
    Запускаем обработку изображения товара после сохранения.
    """
    if instance.image:
        # Запускаем асинхронную обработку
        process_product_image.delay(instance.id)

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля через Celery
    """
    send_email_task.delay(
        subject=f"Password Reset Token for {reset_password_token.user}",
        message=reset_password_token.key,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[reset_password_token.user.email]
    )

@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """
    Отправка письма с подтверждением почты через Celery
    (только для новых пользователей)
    """
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        
        send_email_task.delay(
            subject=f"Подтверждение регистрации для {instance.email}",
            message=f"Ваш токен подтверждения: {token.key}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[instance.email]
        )

@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    Отправка письма при создании нового заказа через Celery
    """
    order_id = kwargs.get('order_id', '')
    
    try:
        user = User.objects.get(id=user_id)
        send_email_task.delay(
            subject="Обновление статуса заказа",
            message=f'Заказ #{order_id} сформирован' if order_id else 'Заказ сформирован',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email]
        )
    except User.DoesNotExist:
        pass  # Логирование ошибки можно добавить при необходимости