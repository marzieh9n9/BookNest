from rest_framework import serializers
from .models import Book, Order, OrderItem
from django.db import transaction







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

    items = OrderItemSerializer(many=True, allow_empty=False)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "status",
            "created_at",
            "updated_at",
            "items",
            "total_price",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "created_at",
            "updated_at",
            "total_price",
        ]

    def validate(self, attrs):
        items_data = attrs.get("items", [])

        book_ids = [
            item["book"].id
            for item in items_data
        ]

        if len(book_ids) != len(set(book_ids)):
            raise serializers.ValidationError(
                "A book can appear only once in an order."
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")

        # Lock books in a consistent order to avoid
        # conflicting simultaneous stock updates.
        book_ids = sorted({
            item["book"].pk for item in items_data
        })

        locked_books = {
            book.pk: book
            for book in Book.objects.select_for_update()
            .filter(pk__in=book_ids)
            .order_by("pk")
        }

        if len(locked_books) != len(book_ids):
            raise serializers.ValidationError(
                {"items": "One or more books no longer exist."}
            )

        # Check the latest stock before creating anything.
        for item_data in items_data:
            book = locked_books[item_data["book"].pk]
            quantity = item_data["quantity"]

            if quantity > book.stock:
                raise serializers.ValidationError({
                    "items": (
                        f"Not enough stock for '{book.title}'. "
                        f"Available: {book.stock}."
                    )
                })

        order = Order.objects.create(
            user=self.context["request"].user
        )

        for item_data in items_data:
            book = locked_books[item_data["book"].pk]
            quantity = item_data["quantity"]

            OrderItem.objects.create(
                order=order,
                book=book,
                quantity=quantity,
                unit_price=book.price,
            )

            book.stock -= quantity
            book.save(update_fields=["stock"])

        return order
