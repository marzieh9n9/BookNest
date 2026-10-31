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

    PAYMENT_STATUS_CHOICES =[("unpaid", "Unpaid"),("paid", "Paid"),]
    
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

    payment_status = models.CharField(
    max_length=20,
    choices=PAYMENT_STATUS_CHOICES,
    default="unpaid",
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    recipient_first_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    recipient_last_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    shipping_address = models.TextField(
        blank=True,
        default="",
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




class PasswordResetCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_codes",
    )

    # Store a hash of the OTP, never the plain code.
    code_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    verified_at = models.DateTimeField(null=True,blank=True,)

    
    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Password reset code for user {self.user_id}"



# ==================================================
# Shopping cart
# ==================================================

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for user {self.user_id}"

    @property
    def total_price(self):
        return sum(
            (
                item.line_total
                for item in self.items.select_related("book").all()
            ),
            Decimal("0.00"),
        )


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "book"],
                name="unique_book_per_cart",
            )
        ]

    def __str__(self):
        return f"{self.book.title} x {self.quantity}"

    @property
    def line_total(self):
        return self.book.price * self.quantity



class UserAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    label = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    recipient_first_name = models.CharField(
        max_length=100,
    )

    recipient_last_name = models.CharField(
        max_length=100,
    )

    phone_number = models.CharField(
        max_length=20,
    )

    city = models.CharField(
        max_length=100,
    )

    postal_code = models.CharField(
        max_length=20,
    )

    address_line = models.TextField()

    is_default = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ("-is_default", "-updated_at")

        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="unique_default_user_address",
            )
        ]

    def __str__(self):
        return (
            f"{self.recipient_first_name} "
            f"{self.recipient_last_name} - {self.city}"
        )
