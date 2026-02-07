from typing import Type
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User
from backend.tasks import send_email_task  # Импортируем Celery задачу

new_user_registered = Signal()
new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля через Celery
    """
    # Используем Celery задачу вместо синхронной отправки
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
    # Получаем order_id из kwargs, если есть
    order_id = kwargs.get('order_id', '')
    
    send_email_task.delay(
        subject="Обновление статуса заказа",
        message=f'Заказ #{order_id} сформирован' if order_id else 'Заказ сформирован',
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[User.objects.get(id=user_id).email]
    )