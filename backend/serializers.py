from rest_framework import serializers
from backend.models import (
    User, Category, Shop, ProductInfo, Product, 
    ProductParameter, OrderItem, Order, Contact,
    ProductImage  # Добавляем импорт
)

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'user', 'phone')
        read_only_fields = ('id',)
        extra_kwargs = {
            'user': {'write_only': True}
        }

class UserSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(read_only=True, many=True)
    avatar_url = serializers.SerializerMethodField()
    avatar_thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'company', 
                 'position', 'contacts', 'avatar_url', 'avatar_thumbnail_url')
        read_only_fields = ('id',)
    
    def get_avatar_url(self, obj):
        """Возвращает URL основного аватара"""
        if obj.avatar:
            return obj.avatar.url
        return None
    
    def get_avatar_thumbnail_url(self, obj):
        """Возвращает URL миниатюры аватара"""
        if obj.avatar:
            # Используем avatar_thumbnail из модели
            return obj.avatar_thumbnail.url
        return None

class ProductImageSerializer(serializers.ModelSerializer):
    """Сериализатор для изображений товара"""
    original_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    product_card_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductImage
        fields = ('id', 'original_url', 'thumbnail_url', 'product_card_url', 'is_main')
    
    def get_original_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
    
    def get_thumbnail_url(self, obj):
        if obj.image:
            # Используем thumbnail из модели ProductImage
            return obj.thumbnail.url
        return None
    
    def get_product_card_url(self, obj):
        if obj.image:
            # Используем product_card из модели ProductImage
            return obj.product_card.url
        return None

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name',)
        read_only_fields = ('id',)

class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'state',)
        read_only_fields = ('id',)

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    images = ProductImageSerializer(many=True, read_only=True)
    main_image = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ('id', 'name', 'category', 'images', 'main_image')
    
    def get_main_image(self, obj):
        """Возвращает основное изображение товара"""
        main_image = obj.images.filter(is_main=True).first()
        if main_image:
            return ProductImageSerializer(main_image).data
        # Если нет основного, возвращаем первое
        first_image = obj.images.first()
        if first_image:
            return ProductImageSerializer(first_image).data
        return None

class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value',)

class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

    class Meta:
        model = ProductInfo
        fields = ('id', 'model', 'product', 'shop', 'quantity', 'price', 'price_rrc', 'product_parameters',)
        read_only_fields = ('id',)

class OrderItemSerializer(serializers.ModelSerializer):
    product_info = ProductInfoSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'total_price')
        read_only_fields = ('id',)
    
    def get_total_price(self, obj):
        """Общая стоимость позиции"""
        return obj.quantity * obj.product_info.price

class OrderItemCreateSerializer(serializers.ModelSerializer):
    """Для создания заказа - принимает ID товара"""
    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'order')
        extra_kwargs = {
            'order': {'write_only': True}
        }

class OrderSerializer(serializers.ModelSerializer):
    ordered_items = OrderItemSerializer(read_only=True, many=True)
    total_sum = serializers.SerializerMethodField()
    contact = ContactSerializer(read_only=True)
    
    class Meta:
        model = Order
        fields = ('id', 'ordered_items', 'state', 'dt', 'total_sum', 'contact')
        read_only_fields = ('id',)
    
    def get_total_sum(self, obj):
        """Общая сумма заказа"""
        total = 0
        for item in obj.ordered_items.all():
            total += item.quantity * item.product_info.price
        return total