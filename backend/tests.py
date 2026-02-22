"""
Тесты для дипломного проекта
"""
import os
os.environ['CELERY_TASK_ALWAYS_EAGER'] = 'True'  # Отключаем асинхронные задачи

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from backend.models import Shop, Category, Product
from rest_framework.authtoken.models import Token
from django.core.cache import cache
from rest_framework import status
from unittest.mock import patch

User = get_user_model()


class SimpleAPITests(TestCase):
    """Простые API тесты"""
    
    def setUp(self):
        # Отключаем сигналы перед тестами
        from django.db.models.signals import post_save
        from backend import signals
        post_save.disconnect(signals.new_user_registered_signal, sender=User)
        
        # Очищаем базу
        Category.objects.all().delete()
        Shop.objects.all().delete()
        
        self.client = APIClient()
        
    def tearDown(self):
        # Включаем сигналы после тестов
        from django.db.models.signals import post_save
        from backend import signals
        post_save.connect(signals.new_user_registered_signal, sender=User)
    
    def test_categories_endpoint_empty(self):
        """Тест endpoint категорий (пустой)"""
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)
    
    def test_categories_endpoint_with_data(self):
        """Тест endpoint категорий с данными"""
        # Создаем тестовые данные
        Category.objects.create(name='Электроника')
        Category.objects.create(name='Одежда')
        
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        
        # Проверяем структуру данных
        for category in data:
            self.assertIn('id', category)
            self.assertIn('name', category)
    
    def test_shops_endpoint_empty(self):
        """Тест endpoint магазинов (пустой)"""
        response = self.client.get('/api/v1/shops')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)
    
    def test_shops_endpoint_with_data(self):
        """Тест endpoint магазинов с данными"""
        # Создаем только активные магазины
        Shop.objects.create(name='Магазин 1', state=True)
        Shop.objects.create(name='Магазин 2', state=True)
        Shop.objects.create(name='Неактивный магазин', state=False)  # Не должен отображаться
        
        response = self.client.get('/api/v1/shops')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Должны быть только активные магазины (state=True)
        self.assertEqual(len(data), 2)
        
        for shop in data:
            self.assertTrue(shop['state'])
            self.assertIn('id', shop)
            self.assertIn('name', shop)
            self.assertIn('state', shop)
    
    def test_products_endpoint(self):
        """Тест endpoint товаров"""
        response = self.client.get('/api/v1/products')
        self.assertEqual(response.status_code, 200)
    
    def test_public_endpoints(self):
        """Тест всех публичных endpoints"""
        endpoints = ['/categories', '/shops', '/products']
        for endpoint in endpoints:
            response = self.client.get(f'/api/v1{endpoint}')
            self.assertEqual(response.status_code, 200)


class ModelTests(TestCase):
    """Тесты моделей"""
    
    def setUp(self):
        # Отключаем сигналы перед тестами
        from django.db.models.signals import post_save
        from backend import signals
        post_save.disconnect(signals.new_user_registered_signal, sender=User)
        
        # Очищаем базу
        Category.objects.all().delete()
        Shop.objects.all().delete()
        Product.objects.all().delete()
        User.objects.all().delete()
    
    def tearDown(self):
        # Включаем сигналы после тестов
        from django.db.models.signals import post_save
        from backend import signals
        post_save.connect(signals.new_user_registered_signal, sender=User)
    
    def test_create_user_without_signals(self):
        """Создание пользователя без сигналов"""
        user = User.objects.create_user(
            email='test@example.com',
            password='test123',
            first_name='Тест',
            last_name='Тестов'
        )
        user.is_active = True
        user.save()
        
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(str(user), 'Тест Тестов')
    
    def test_create_shop(self):
        """Создание магазина"""
        shop = Shop.objects.create(name='Тестовый магазин', state=True)
        self.assertEqual(Shop.objects.count(), 1)
        self.assertEqual(str(shop), 'Тестовый магазин')
        self.assertTrue(shop.state)
    
    def test_create_category(self):
        """Создание категории"""
        category = Category.objects.create(name='Электроника')
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(str(category), 'Электроника')
    
    def test_create_product(self):
        """Создание продукта"""
        category = Category.objects.create(name='Электроника')
        product = Product.objects.create(
            name='Смартфон',
            category=category
        )
        
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(product.name, 'Смартфон')
        self.assertEqual(product.category.name, 'Электроника')


class AuthenticationTests(TestCase):
    """Тесты аутентификации"""
    
    def setUp(self):
        # Отключаем сигналы
        from django.db.models.signals import post_save
        from backend import signals
        post_save.disconnect(signals.new_user_registered_signal, sender=User)
        
        # Очищаем базу
        User.objects.all().delete()
        
        # Создаем пользователя напрямую
        self.user = User.objects.create_user(
            email='auth@test.com',
            password='auth123',
            first_name='Auth',
            last_name='Test',
            is_active=True
        )
        
        self.client = APIClient()
    
    def tearDown(self):
        # Включаем сигналы
        from django.db.models.signals import post_save
        from backend import signals
        post_save.connect(signals.new_user_registered_signal, sender=User)
    
    def test_user_login(self):
        """Тест авторизации"""
        data = {
            'email': 'auth@test.com',
            'password': 'auth123'
        }
        response = self.client.post('/api/v1/user/login', data, format='json')
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        # Проверяем структуру ответа
        self.assertIn('Status', result)
        self.assertIn('Token', result)
        self.assertTrue(result['Status'])
    
    def test_user_details_unauthorized(self):
        """Тест получения данных пользователя без авторизации"""
        response = self.client.get('/api/v1/user/details')
        
        # Должен быть 403 (Forbidden)
        self.assertEqual(response.status_code, 403)
        result = response.json()
        self.assertFalse(result['Status'])
        self.assertEqual(result['Error'], 'Log in required')
    
    def test_user_details_authorized(self):
        """Тест получения данных пользователя с авторизацией"""
        # Сначала авторизуемся
        login_data = {
            'email': 'auth@test.com',
            'password': 'auth123'
        }
        login_response = self.client.post('/api/v1/user/login', login_data, format='json')
        token = login_response.json()['Token']
        
        # Получаем данные с токеном
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/v1/user/details')
        
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['email'], 'auth@test.com')
        self.assertEqual(data['first_name'], 'Auth')
        self.assertEqual(data['last_name'], 'Test')
class ThrottlingTests(TestCase):
    """Тесты для тротлинга"""
    
    def setUp(self):
        # Отключаем сигналы
        from django.db.models.signals import post_save
        from backend import signals
        post_save.disconnect(signals.new_user_registered_signal, sender=User)
        
        # Очищаем кэш перед каждым тестом
        cache.clear()
        
        self.client = APIClient()
        
        # Создаем тестового пользователя
        self.user = User.objects.create_user(
            email='throttle@test.com',
            password='throttle123',
            first_name='Throttle',
            last_name='Test',
            is_active=True
        )
        
        # Создаем магазин для тестов импорта
        self.shop = Shop.objects.create(
            name='Throttle Shop',
            user=self.user,
            state=True
        )
    
    def tearDown(self):
        # Включаем сигналы
        from django.db.models.signals import post_save
        from backend import signals
        post_save.connect(signals.new_user_registered_signal, sender=User)
        cache.clear()
    
    def test_register_throttling(self):
        """Тест ограничения на регистрацию"""
        from django.conf import settings
        old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['register'] = '1/minute'
        
        # Очищаем кэш перед тестом
        cache.clear()
        
        # Создаем клиент с фиксированным IP
        client = APIClient(REMOTE_ADDR='127.0.0.1')
        
        data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@test.com',
            'password': 'TestPass123!',
            'company': 'Test Company',
            'position': 'Tester'
        }
        
        # Первый запрос должен быть успешным
        response = client.post('/api/v1/user/register', data, format='json')
        print(f"Register response 1: {response.status_code} - {response.content}")
        self.assertEqual(response.status_code, 200)
        
        # Второй запрос должен получить 429
        data['email'] = 'test2@test.com'  # Меняем email
        response = client.post('/api/v1/user/register', data, format='json')
        print(f"Register response 2: {response.status_code} - {response.content}")
        self.assertEqual(response.status_code, 429)
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates

    def test_login_throttling(self):
        """Тест ограничения на вход"""
        from django.conf import settings
        old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login'] = '1/minute'
        
        # Очищаем кэш перед тестом
        cache.clear()
        
        data = {
            'email': 'throttle@test.com',
            'password': 'wrong_password'
        }
        
        # Первая попытка
        response = self.client.post('/api/v1/user/login', data, format='json')
        print(f"Login response 1: {response.status_code} - {response.content}")  # Отладка
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['Status'])
        
        # Вторая попытка - должна быть отклонена
        response = self.client.post('/api/v1/user/login', data, format='json')
        print(f"Login response 2: {response.status_code} - {response.content}")  # Отладка
        self.assertEqual(response.status_code, 429)
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates

    def test_login_throttling(self):
        """Тест ограничения на вход"""
        from django.conf import settings
        old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login'] = '1/minute'
        
        data = {
            'email': 'throttle@test.com',
            'password': 'wrong_password'
        }
        
        # Первая попытка - должна вернуть 200 с Status=False
        response = self.client.post('/api/v1/user/login', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['Status'])
        
        # Вторая попытка - должна быть отклонена тротлингом
        response = self.client.post('/api/v1/user/login', data, format='json')
        self.assertEqual(response.status_code, 429)
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates
    
def test_import_throttling(self):
    """Тест ограничения на импорт для магазинов"""
    from django.conf import settings
    old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
    settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['import'] = '1/day'
    
    # Важно: Убедимся, что пользователь имеет тип 'shop'
    self.user.type = 'shop'
    self.user.save()
    
    # Авторизуемся как владелец магазина
    token, _ = Token.objects.get_or_create(user=self.user)
    self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    test_url = 'https://example.com/test.yaml'
    
    # Патчим get запрос
    with patch('requests.get') as mock_get:
        mock_get.return_value.content = b"""
shop: Test Shop
categories:
  - id: 1
    name: Test Category
goods:
  - id: 1
    category: 1
    model: test/model
    name: Test Product
    price: 100
    price_rrc: 120
    quantity: 10
    parameters:
      "test": "value"
"""
        
        data = {'url': test_url}
        
        # Первый импорт должен быть успешным
        response = self.client.post('/api/v1/partner/update', data, format='json')
        print(f"Import response 1: {response.status_code} - {response.content}")  # Отладка
        self.assertEqual(response.status_code, 200)
        
        # Второй импорт должен получить 429
        response = self.client.post('/api/v1/partner/update', data, format='json')
        print(f"Import response 2: {response.status_code} - {response.content}")  # Отладка
        self.assertEqual(response.status_code, 429)
    
    settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates   
    def test_user_rate_throttle(self):
        """Тест общего ограничения для авторизованных пользователей"""
        from django.conf import settings
        old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
        
        # Временно меняем настройки
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['user'] = '1/minute'
        
        # Авторизуемся
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        # Первый запрос должен быть успешным
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        
        # Второй запрос должен быть отклонен
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 429)
        
        # Восстанавливаем настройки
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates
    
    def test_anon_rate_throttle(self):
        """Тест общего ограничения для анонимных пользователей"""
        from django.conf import settings
        old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['anon'] = '1/minute'
        
        # Без авторизации
        # Первый запрос должен быть успешным
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        
        # Второй запрос должен быть отклонен
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 429)
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates
    
    def test_throttle_headers(self):
        """Проверяем, что возвращаются правильные headers при тротлинге"""
        from django.conf import settings
        old_rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].copy()
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['anon'] = '1/minute'
        
        # Первый запрос
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        
        # Второй запрос - должен быть отклонен
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 429)
        
        # Проверяем headers
        self.assertIn('Retry-After', response)
        
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = old_rates