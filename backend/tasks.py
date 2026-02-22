from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from yaml import load as load_yaml, Loader
from requests import get
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_user_avatar(user_id):
    """
    Асинхронная обработка аватара пользователя.
    Принудительно создаёт миниатюры, обращаясь к ним.
    """
    from .models import User
    
    try:
        user = User.objects.get(id=user_id)
        if user.avatar:
            # Принудительно создаём миниатюры, обращаясь к ним
            if hasattr(user, 'avatar_thumbnail'):
                thumbnail_url = user.avatar_thumbnail.url
                logger.info(f"Avatar thumbnail created for user {user_id}: {thumbnail_url}")
            
            return {'status': 'success', 'user_id': user_id, 'message': 'Avatar processed'}
        return {'status': 'warning', 'user_id': user_id, 'message': 'No avatar to process'}
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'status': 'error', 'message': 'User not found'}
    except Exception as e:
        logger.error(f"Error processing avatar for user {user_id}: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@shared_task
def process_product_image(image_id):
    """
    Асинхронная обработка изображения товара.
    Принудительно создаёт все версии, обращаясь к ним.
    """
    from .models import ProductImage
    
    try:
        image = ProductImage.objects.get(id=image_id)
        if image.image:
            # Принудительно создаём все версии, обращаясь к ним
            created_versions = []
            
            if hasattr(image, 'thumbnail'):
                thumbnail_url = image.thumbnail.url
                created_versions.append('thumbnail')
                logger.info(f"Thumbnail created for image {image_id}: {thumbnail_url}")
            
            if hasattr(image, 'product_card'):
                product_card_url = image.product_card.url
                created_versions.append('product_card')
                logger.info(f"Product card created for image {image_id}: {product_card_url}")
            
            if hasattr(image, 'cart_preview'):
                cart_preview_url = image.cart_preview.url
                created_versions.append('cart_preview')
                logger.info(f"Cart preview created for image {image_id}: {cart_preview_url}")
            
            return {
                'status': 'success', 
                'image_id': image_id, 
                'created_versions': created_versions
            }
        return {'status': 'warning', 'image_id': image_id, 'message': 'No image to process'}
    except ProductImage.DoesNotExist:
        logger.error(f"Product image {image_id} not found")
        return {'status': 'error', 'message': 'Image not found'}
    except Exception as e:
        logger.error(f"Error processing image {image_id}: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@shared_task
def send_email_task(subject, message, from_email, recipient_list):
    """Асинхронная отправка email"""
    try:
        msg = EmailMultiAlternatives(subject, message, from_email, recipient_list)
        msg.send()
        logger.info(f"Email sent to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

@shared_task
def import_products_task(url, user_id):
    """Асинхронный импорт товаров"""
    from .models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter
    
    try:
        # Получаем данные по URL
        stream = get(url).content
        data = load_yaml(stream, Loader=Loader)
        
        # Создаем или обновляем магазин
        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user_id)
        
        # Обрабатываем категории
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(
                id=category['id'], 
                name=category['name']
            )
            category_object.shops.add(shop.id)
            category_object.save()
        
        # Удаляем старые товары
        ProductInfo.objects.filter(shop_id=shop.id).delete()
        
        # Добавляем новые товары
        imported_count = 0
        for item in data['goods']:
            product, _ = Product.objects.get_or_create(
                name=item['name'], 
                category_id=item['category']
            )
            
            product_info = ProductInfo.objects.create(
                product_id=product.id,
                external_id=item['id'],
                model=item['model'],
                price=item['price'],
                price_rrc=item['price_rrc'],
                quantity=item['quantity'],
                shop_id=shop.id
            )
            
            # Добавляем параметры
            for name, value in item['parameters'].items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(
                    product_info_id=product_info.id,
                    parameter_id=parameter_object.id,
                    value=value
                )
            
            imported_count += 1
        
        logger.info(f"Successfully imported {imported_count} products for shop {shop.id}")
        return {"status": "success", "imported": imported_count}
    
    except Exception as e:
        logger.error(f"Error importing products: {str(e)}")
        return {"status": "error", "message": str(e)}