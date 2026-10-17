from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    stock = models.IntegerField(
        validators=[MinValueValidator(0)]
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="books",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.title


class Order(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user}"

    @property
    def total_price(self):
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00")
        )


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="order_items"
    )

    quantity = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    def __str__(self):
        return f"{self.book.title} x {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "book"],
                name="unique_book_per_order"
            )
        ]

