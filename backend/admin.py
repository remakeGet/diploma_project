from django.contrib import admin
from django.utils.html import format_html
from .models import (
    User, Shop, Category, Product, ProductInfo, 
    Order, OrderItem, Contact, ProductParameter,
    ProductImage  # Добавляем импорт новой модели
)

class ProductImageInline(admin.TabularInline):
    """Инлайн для изображений товара"""
    model = ProductImage
    extra = 1
    fields = ('image', 'is_main', 'image_preview')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        """Превью изображения в админке"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.image.url
            )
        return "Нет изображения"
    image_preview.short_description = 'Превью'

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'position', 'type', 'is_active', 'avatar_preview')
    list_filter = ('type', 'is_active', 'company')
    search_fields = ('email', 'first_name', 'last_name', 'company')
    ordering = ('email',)
    readonly_fields = ('avatar_preview',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('email', 'first_name', 'last_name', 'type')
        }),
        ('Профессиональная информация', {
            'fields': ('company', 'position'),
            'classes': ('baton-tabs-item',),
        }),
        ('Аватар', {
            'fields': ('avatar', 'avatar_preview'),
            'classes': ('baton-tabs-item',),
            'description': 'Поддерживаются форматы JPG, PNG, GIF'
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('baton-tabs-item',),
        }),
    )
    
    def avatar_preview(self, obj):
        """Превью аватара в админке"""
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 50%;" />',
                obj.avatar_thumbnail.url if hasattr(obj, 'avatar_thumbnail') else obj.avatar.url
            )
        return "Нет аватара"
    avatar_preview.short_description = 'Превью аватара'

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'state', 'url')
    list_filter = ('state', 'categories')
    search_fields = ('name', 'user__email')
    autocomplete_fields = ('user',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_shop_count')
    search_fields = ('name',)
    filter_horizontal = ('shops',)
    
    def get_shop_count(self, obj):
        return obj.shops.count()
    get_shop_count.short_description = 'Количество магазинов'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'get_product_count', 'get_first_image')
    list_filter = ('category',)
    search_fields = ('name',)
    autocomplete_fields = ('category',)
    inlines = [ProductImageInline]
    
    def get_product_count(self, obj):
        return obj.product_infos.count()
    get_product_count.short_description = 'Вариаций товара'
    
    def get_first_image(self, obj):
        """Показывает первое изображение товара"""
        first_image = obj.images.first()
        if first_image and first_image.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
                first_image.thumbnail.url if hasattr(first_image, 'thumbnail') else first_image.image.url
            )
        return "Нет фото"
    get_first_image.short_description = 'Фото'

class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 1

@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('product', 'shop', 'model', 'price', 'price_rrc', 'quantity')
    list_filter = ('shop', 'product__category')
    search_fields = ('product__name', 'model')
    autocomplete_fields = ('product', 'shop')
    inlines = [ProductParameterInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ('product_info',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'dt', 'state', 'contact')
    list_filter = ('state', 'dt')
    search_fields = ('user__email', 'contact__phone')
    autocomplete_fields = ('user', 'contact')
    inlines = [OrderItemInline]
    date_hierarchy = 'dt'

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'street', 'house', 'phone')
    list_filter = ('city',)
    search_fields = ('user__email', 'phone', 'city')

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Отдельная админка для изображений товаров"""
    list_display = ('id', 'product', 'is_main', 'image_preview')
    list_filter = ('is_main', 'product__category')
    search_fields = ('product__name',)
    autocomplete_fields = ('product',)
    list_editable = ('is_main',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.thumbnail.url if hasattr(obj, 'thumbnail') else obj.image.url
            )
        return "Нет изображения"
    image_preview.short_description = 'Превью'