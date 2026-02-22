from django.contrib import admin
from django.utils.html import format_html
from .models import User, Shop, Category, Product, ProductInfo, Order, OrderItem, Contact, ProductParameter

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'position', 'type', 'is_active')
    list_filter = ('type', 'is_active', 'company')
    search_fields = ('email', 'first_name', 'last_name', 'company')
    ordering = ('email',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('email', 'first_name', 'last_name', 'type')
        }),
        ('Профессиональная информация', {
            'fields': ('company', 'position'),
            'classes': ('baton-tabs-item',),  # Добавляем таб
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('baton-tabs-item',),
        }),
    )

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
    list_display = ('name', 'category', 'get_product_count')
    list_filter = ('category',)
    search_fields = ('name',)
    autocomplete_fields = ('category',)
    
    def get_product_count(self, obj):
        return obj.product_infos.count()
    get_product_count.short_description = 'Вариаций товара'

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