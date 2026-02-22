from django.conf import settings
import time
from django.db import connection
from .models import ProductInfo, Shop, Category

from distutils.util import strtobool
from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from requests import get
from django.shortcuts import render  # 
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from backend.throttles import RegisterThrottle, LoginThrottle, ImportThrottle
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken
from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer
from backend.signals import new_user_registered, new_order


class SocialLoginPage(APIView):
    """Страница с кнопками входа через соцсети"""
    
    def get(self, request):
        return render(request, 'social_login.html')
    
class SocialLoginSuccess(APIView):
    """
    Обработка успешного входа через соцсети.
    Возвращает токен для API.
    """
    def get(self, request):
        user = request.user
        if user.is_authenticated:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'Status': True,
                'Token': token.key,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
        return Response({
            'Status': False,
            'Error': 'Not authenticated'
        }, status=401)

class SocialLoginError(APIView):
    """
    Обработка ошибки при входе через соцсети.
    """
    def get(self, request):
        return Response({
            'Status': False,
            'Error': 'Social authentication failed'
        }, status=400)

class RegisterAccount(APIView):
    """
    Регистрация нового покупателя.
    
    Создает нового пользователя с ролью покупателя.
    После регистрации требуется подтверждение email через токен.
    
    POST параметры:
    - first_name: Имя (обязательно)
    - last_name: Фамилия (обязательно)
    - email: Email (обязательно, уникальный)
    - password: Пароль (обязательно)
    - company: Компания (обязательно)
    - position: Должность (обязательно)
    
    Returns:
    - Status: True при успешной регистрации
    - Errors: Описание ошибок при неудаче
    """    
    throttle_classes = [RegisterThrottle]
    # Регистрация методом POST

    def post(self, request, *args, **kwargs):
        """
            Process a POST request and create a new user.

            Args:
                request (Request): The Django request object.

            Returns:
                JsonResponse: The response indicating the status of the operation and any errors.
            """
        print(f"RegisterAccount called with throttle_classes: {self.throttle_classes}")
        print(f"Request IP: {request.META.get('REMOTE_ADDR')}")
        # Проверяем троттлинг вручную для отладки
        for throttle in self.get_throttles():
            if not throttle.allow_request(request, self):
                print(f"Throttle {throttle} blocked the request")
        # проверяем обязательные аргументы
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):

            # проверяем пароль на сложность
            # sad = 'asd'
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяем данные для уникальности имени пользователя

                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
                Подтверждает почтовый адрес пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        # проверяем обязательные аргументы
        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class AccountDetails(APIView):
    """
    A class for managing user account details.

    Methods:
    - get: Retrieve the details of the authenticated user.
    - post: Update the account details of the authenticated user.

    Attributes:
    - None
    """

    # получить данные
    def get(self, request: Request, *args, **kwargs):
        """
               Retrieve the details of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        """
                Update the account details of the authenticated user.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        # проверяем обязательные аргументы

        if 'password' in request.data:
            errors = {}
            # проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])

        # проверяем остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """
    throttle_classes = [LoginThrottle]
    # Авторизация методом POST
    def post(self, request, *args, **kwargs):
        """
                Authenticate a user.

                Args:
                    request (Request): The Django request object.

                Returns:
                    JsonResponse: The response indicating the status of the operation and any errors.
                """
        print(f"LoginAccount called with throttle_classes: {self.throttle_classes}")
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'], password=request.data['password'])

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)

                    return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
        A class for searching products.

        Methods:
        - get: Retrieve the product information based on the specified filters.

        Attributes:
        - None
        """

    def get(self, request: Request, *args, **kwargs):
        """
               Retrieve the product information based on the specified filters.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the product information.
               """
        # Очищаем список запросов к БД для чистоты эксперимента
        connection.queries_log.clear()
        
        # Засекаем время начала
        start_time = time.time()
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дуликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)
# Засекаем время конца
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # в миллисекундах
        
        # Считаем количество запросов к БД
        num_queries = len(connection.queries)
        
        # Выводим результаты в консоль Django
        print(f"\n{'='*50}")
        print(f"📊 ProductInfoView Performance:")
        print(f"⏱️  Время выполнения: {duration:.2f} ms")
        print(f"🗄️  Запросов к БД: {num_queries}")
        print(f"{'='*50}\n")
        
        # Можно добавить информацию в заголовки ответа
        response = Response(serializer.data)
        response['X-Query-Count'] = num_queries
        response['X-Response-Time'] = f"{duration:.2f}ms"
        return Response(serializer.data)


class BasketView(APIView):
    """
    Управление корзиной покупок пользователя.
    
    GET: Получить содержимое корзины
    POST: Добавить товары в корзину
    PUT: Обновить количество товаров в корзине
    DELETE: Удалить товары из корзины
    
    Требуется аутентификация.
    """
    """
    A class for managing the user's shopping basket.

    Methods:
    - get: Retrieve the items in the user's basket.
    - post: Add an item to the user's basket.
    - put: Update the quantity of an item in the user's basket.
    - delete: Remove an item from the user's basket.

    Attributes:
    - None
    """

    # получить корзину
    def get(self, request, *args, **kwargs):
        """"
        Получить содержимое корзины.
        
        Возвращает список товаров в корзине пользователя с общей суммой.
        
        Returns:
        - 200: Список позиций в корзине
        - 403: Если пользователь не аутентифицирован
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # редактировать корзину
    def post(self, request, *args, **kwargs):
        """
               Add an items to the user's basket.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)})
                        else:
                            objects_created += 1

                    else:

                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

                return JsonResponse({'Status': True, 'Создано объектов': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить товары из корзины
    def delete(self, request, *args, **kwargs):
        """
                Remove  items from the user's basket.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # добавить позиции в корзину
    def put(self, request, *args, **kwargs):
        """
        Обновить количество товаров в корзине.
        
        Ожидает JSON с items, содержащими id позиции и новое количество:
        {
            "items": "[{\"id\": 1, \"quantity\": 5}]"
        }
        
        Returns:
        - Status: True при успешном обновлении
        - Обновлено объектов: Количество обновленных позиций
        - Errors: Описание ошибок при неудаче
        English version:
        Update the quantity of items in the user's basket.
        
        Args:
        - request (Request): The Django request object.
        
        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if 'id' in order_item and 'quantity' in order_item:
                        # Проверяем, что позиция принадлежит корзине текущего пользователя
                        updated = OrderItem.objects.filter(
                            order_id=basket.id, 
                            id=order_item['id']
                        ).update(quantity=order_item['quantity'])
                        if updated:
                            objects_updated += 1
                
                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})    

class PartnerUpdate(APIView):
    """
    A class for updating partner information.

    Methods:
    - post: Update the partner information.

    Attributes:
    - None
    """
    throttle_classes = [ImportThrottle]
    def post(self, request, *args, **kwargs):
        """
                Update the partner price list information.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})
            else:
                stream = get(url).content

                data = load_yaml(stream, Loader=Loader)

                shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
                for category in data['categories']:
                    category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                    category_object.shops.add(shop.id)
                    category_object.save()
                ProductInfo.objects.filter(shop_id=shop.id).delete()
                for item in data['goods']:
                    product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

                    product_info = ProductInfo.objects.create(product_id=product.id,
                                                              external_id=item['id'],
                                                              model=item['model'],
                                                              price=item['price'],
                                                              price_rrc=item['price_rrc'],
                                                              quantity=item['quantity'],
                                                              shop_id=shop.id)
                    for name, value in item['parameters'].items():
                        parameter_object, _ = Parameter.objects.get_or_create(name=name)
                        ProductParameter.objects.create(product_info_id=product_info.id,
                                                        parameter_id=parameter_object.id,
                                                        value=value)

                return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerState(APIView):
    """
       A class for managing partner state.

       Methods:
       - get: Retrieve the state of the partner.

       Attributes:
       - None
       """
    # получить текущий статус
    def get(self, request, *args, **kwargs):
        """
               Retrieve the state of the partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the state of the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменить текущий статус
    def post(self, request, *args, **kwargs):
        """
               Update the state of a partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)
        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strtobool(state))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
     Methods:
    - get: Retrieve the orders associated with the authenticated partner.

    Attributes:
    - None
    """

    def get(self, request, *args, **kwargs):
        """
               Retrieve the orders associated with the authenticated partner.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the orders associated with the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """
       A class for managing contact information.

       Methods:
       - get: Retrieve the contact information of the authenticated user.
       - post: Create a new contact for the authenticated user.
       - put: Update the contact information of the authenticated user.
       - delete: Delete the contact of the authenticated user.

       Attributes:
       - None
       """

    # получить мои контакты
    def get(self, request, *args, **kwargs):
        """
               Retrieve the contact information of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the contact information.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавить новый контакт
    def post(self, request, *args, **kwargs):
        """
               Create a new contact for the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'city', 'street', 'phone'}.issubset(request.data):
            request.data._mutable = True
            request.data.update({'user': request.user.id})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить контакт
    def delete(self, request, *args, **kwargs):
        """
               Delete the contact of the authenticated user.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # редактировать контакт
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            """
                   Update the contact information of the authenticated user.

                   Args:
                   - request (Request): The Django request object.

                   Returns:
                   - JsonResponse: The response indicating the status of the operation and any errors.
                   """
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class OrderView(APIView):
    """
    Класс для получения и размешения заказов пользователями
    Methods:
    - get: Retrieve the details of a specific order.
    - post: Create a new order.
    - put: Update the details of a specific order.
    - delete: Delete a specific order.

    Attributes:
    - None
    """

    # получить мои заказы
    def get(self, request, *args, **kwargs):
        """
               Retrieve the details of user orders.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the order.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    # разместить заказ из корзины
def post(self, request, *args, **kwargs):
    """Разместить заказ из корзины"""
    if not request.user.is_authenticated:
        return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

    if {'id', 'contact'}.issubset(request.data):
        if request.data['id'].isdigit():
            try:
                is_updated = Order.objects.filter(
                    user_id=request.user.id, id=request.data['id']
                ).update(
                    contact_id=request.data['contact'],
                    state='new'
                )
            except IntegrityError as error:
                # Ручная отправка ошибки в Hawk с дополнительным контекстом
                hawk.capture_exception(error)
                hawk.set_context("order_creation", {
                    "user_id": request.user.id,
                    "order_id": request.data.get('id'),
                    "contact_id": request.data.get('contact')
                })
                print(error)
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})
            else:
                if is_updated:
                    # Добавляем breadcrumb для успешных операций (опционально)
                    hawk.add_breadcrumb(
                        category='order',
                        message=f'Order {request.data["id"]} created successfully',
                        level='info'
                    )
                    new_order.send(sender=self.__class__, user_id=request.user.id)
                    return JsonResponse({'Status': True})

    return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class HawkDebugView(APIView):
    """Тестовый эндпоинт для проверки работы Hawk"""
    
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        # Просто вызываем исключение
        1 / 0
        return Response({"message": "This will never be reached"})
class SimpleHawkTestView(APIView):
    """Простой тест отправки в Hawk"""
    
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        results = []
        
        # Проверяем наличие hawk
        if not hasattr(settings, 'hawk') or not settings.hawk:
            return Response({
                'status': 'error',
                'message': 'Hawk not initialized',
                'hawk_object': str(getattr(settings, 'hawk', None))
            })
        
        # Пробуем отправить тестовое сообщение
        try:
            # Простое сообщение без ошибки
            result = settings.hawk.send(
                "Test message from SimpleHawkTestView",
                {
                    'url': request.path,
                    'method': request.method,
                    'test': True
                }
            )
            results.append({'type': 'message', 'result': str(result)})
        except Exception as e:
            results.append({'type': 'message', 'error': str(e)})
        
        # Пробуем отправить ошибку
        try:
            try:
                1 / 0
            except Exception as e:
                result = settings.hawk.send(
                    e,
                    {
                        'url': request.path,
                        'method': request.method,
                        'test': True
                    }
                )
                results.append({'type': 'exception', 'result': str(result)})
        except Exception as e:
            results.append({'type': 'exception', 'error': str(e)})
        
        return Response({
            'status': 'completed',
            'hawk_configured': True,
            'hawk_object': str(settings.hawk),
            'results': results
        })
class CacheTestView(APIView):
    """View для демонстрации работы кэширования"""
    
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        results = []
        
        # Тест 1: Первый запрос
        connection.queries_log.clear()
        start = time.time()
        
        categories = list(Category.objects.all())
        shops = list(Shop.objects.filter(state=True))
        products = list(Product.objects.all()[:5])
        
        duration1 = (time.time() - start) * 1000
        queries1 = len(connection.queries)
        
        results.append({
            'test': 'Первый запрос',
            'time_ms': round(duration1, 2),
            'queries': queries1
        })
        
        # Тест 2: Второй запрос (должен быть из кэша)
        connection.queries_log.clear()
        start = time.time()
        
        categories2 = list(Category.objects.all())
        shops2 = list(Shop.objects.filter(state=True))
        products2 = list(Product.objects.all()[:5])
        
        duration2 = (time.time() - start) * 1000
        queries2 = len(connection.queries)
        
        results.append({
            'test': 'Второй запрос (с кэшем)',
            'time_ms': round(duration2, 2),
            'queries': queries2
        })
        
        return Response({
            'status': 'ok',
            'results': results,
            'cache_type': 'Django LocMemCache'
        })