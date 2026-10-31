from rest_framework import serializers
from .models import (Book,Order,OrderItem,Cart,CartItem,UserAddress,)



class BookSerializer(serializers.ModelSerializer):

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Price cannot be negative."
            )
        return value

    def validate_stock(self, value):
        if value > 100:
            raise serializers.ValidationError(
                "Stock cannot be greater than 100."
            )
        return value


    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "price",
            "stock",
            "category",
        ]


class OrderItemSerializer(serializers.ModelSerializer):

    line_total = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "book",
            "quantity",
            "unit_price",
            "line_total",
        ]
        read_only_fields = [
            "unit_price",
            "line_total",
        ]

    def validate(self, data):
        book = data["book"]
        quantity = data["quantity"]

        if quantity > book.stock:
            raise serializers.ValidationError(
                f"Only {book.stock} items are available."
            )

        return data



class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True,
    )

    total_price = serializers.ReadOnlyField()

    class Meta:
        model = Order

        fields = [
            "id",
            "user",
            "status",
            "payment_status",
            "paid_at",
            "recipient_first_name",
            "recipient_last_name",
            "phone_number",
            "city",
            "postal_code",
            "shipping_address",
            "created_at",
            "updated_at",
            "items",
            "total_price",
        ]

        read_only_fields = [
            "id",
            "user",
            "status",
            "payment_status",
            "paid_at",
            "recipient_first_name",
            "recipient_last_name",
            "phone_number",
            "city",
            "postal_code",
            "shipping_address",
            "created_at",
            "updated_at",
            "items",
            "total_price",
        ]


# ==================================================
# Shopping cart serializers
# ==================================================

class CartBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "price",
            "stock",
            "category",
        ]


class CartItemSerializer(serializers.ModelSerializer):
    book = CartBookSerializer(read_only=True)
    line_total = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "book",
            "quantity",
            "line_total",
        ]
        read_only_fields = [
            "id",
            "book",
            "line_total",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(
        many=True,
        read_only=True,
    )

    total_price = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "items",
            "total_price",
            "created_at",
            "updated_at",
        ]


class AddCartItemSerializer(serializers.Serializer):
    book_id = serializers.PrimaryKeyRelatedField(
        source="book",
        queryset=Book.objects.all(),
    )

    quantity = serializers.IntegerField(
        min_value=1,
        max_value=100,
    )


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=100,
    )




class CheckoutSerializer(serializers.Serializer):
    recipient_first_name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )

    recipient_last_name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )

    phone_number = serializers.RegexField(
        regex=r"^\+?[0-9][0-9\s()-]{7,18}$",
        max_length=20,
        error_messages={
            "invalid": "Enter a valid phone number.",
        },
    )

    city = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )

    postal_code = serializers.CharField(
        max_length=20,
        trim_whitespace=True,
    )

    shipping_address = serializers.CharField(
        max_length=1000,
        trim_whitespace=True,
    )

class UserAddressSerializer(serializers.ModelSerializer):
    phone_number = serializers.RegexField(
        regex=r"^\+?[0-9][0-9\s()-]{7,18}$",
        max_length=20,
    )

    class Meta:
        model = UserAddress

        fields = [
            "id",
            "label",
            "recipient_first_name",
            "recipient_last_name",
            "phone_number",
            "city",
            "postal_code",
            "address_line",
            "is_default",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


