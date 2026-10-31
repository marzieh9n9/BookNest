
from django.contrib import admin

from .models import (Book,Category,Order,OrderItem,Cart,CartItem,UserAddress,)

# ==================================================
# Categories
# ==================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


# ==================================================
# Books
# ==================================================

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "author",
        "price",
        "stock",
        "category",
    )

    list_filter = ("category",)
    search_fields = ("title", "author")
    list_editable = ("price", "stock")
    ordering = ("title",)


# ==================================================
# Order items displayed inside an order
# ==================================================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False

    readonly_fields = (
        "book",
        "quantity",
        "unit_price",
        "line_total",
    )

    fields = (
        "book",
        "quantity",
        "unit_price",
        "line_total",
    )

    def has_add_permission(self, request, obj=None):
        return False


# ==================================================
# Orders
# ==================================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "recipient_first_name",
        "recipient_last_name",
        "phone_number",
        "status",
        "payment_status",
        "total_price",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "recipient_first_name",
        "recipient_last_name",
        "phone_number",
        "city",
        "postal_code",
    )

    readonly_fields = (
        "user",
        "payment_status",
        "paid_at",
        "created_at",
        "updated_at",
        "total_price",
    )

    fieldsets = (
        (
            "Order information",
            {
                "fields": (
                    "user",
                    "status",
                    "payment_status",
                    "paid_at",
                    "total_price",
                )
            },
        ),
        (
            "Recipient and delivery",
            {
                "fields": (
                    "recipient_first_name",
                    "recipient_last_name",
                    "phone_number",
                    "city",
                    "postal_code",
                    "shipping_address",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = (OrderItemInline,)
    ordering = ("-created_at",)


# ==================================================
# Order items
# ==================================================

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "book",
        "quantity",
        "unit_price",
        "line_total",
    )

    search_fields = (
        "book__title",
        "order__user__email",
    )

    readonly_fields = (
        "order",
        "book",
        "quantity",
        "unit_price",
        "line_total",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ==================================================
# Cart items
# ==================================================

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    can_delete = False

    readonly_fields = (
        "book",
        "quantity",
        "line_total",
        "created_at",
        "updated_at",
    )

    fields = (
        "book",
        "quantity",
        "line_total",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


# ==================================================
# Shopping carts
# ==================================================

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "item_count",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__email",
        "user__username",
    )

    readonly_fields = (
        "user",
        "created_at",
        "updated_at",
    )

    inlines = (CartItemInline,)

    def item_count(self, obj):
        return obj.items.count()

    item_count.short_description = "Number of items"


# ==================================================
# Customer saved addresses
# ==================================================

@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "recipient_first_name",
        "recipient_last_name",
        "phone_number",
        "city",
        "is_default",
        "updated_at",
    )

    list_filter = (
        "city",
        "is_default",
    )

    search_fields = (
        "user__email",
        "recipient_first_name",
        "recipient_last_name",
        "phone_number",
        "city",
        "postal_code",
    )

    readonly_fields = (
        "user",
        "is_default",
        "created_at",
        "updated_at",
    )
