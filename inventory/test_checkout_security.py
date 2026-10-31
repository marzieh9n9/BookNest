from decimal import Decimal

from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import (
    Book,
    Cart,
    CartItem,
    Order,
    OrderItem,
    UserAddress,
)


User = get_user_model()


class CheckoutSecurityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customer1@example.com",
            email="customer1@example.com",
            password="TestPassword!2026",
        )

        self.other_user = User.objects.create_user(
            username="customer2@example.com",
            email="customer2@example.com",
            password="AnotherTestPassword!2026",
        )

        self.book = Book.objects.create(
            title="Test Book",
            author="Test Author",
            price=Decimal("12.50"),
            stock=5,
        )

        self.client.force_authenticate(
            user=self.user
        )

    def checkout_data(self):
        return {
            "recipient_first_name": "Test",
            "recipient_last_name": "Customer",
            "phone_number": "09123456789",
            "city": "Tehran",
            "postal_code": "1234567890",
            "shipping_address": (
                "Test street, building 1, unit 2"
            ),
        }

    def test_legacy_order_post_is_disabled(self):
        response = self.client.post(
            "/api/orders/",
            self.checkout_data(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_checkout_rejects_empty_cart(self):
        Cart.objects.create(
            user=self.user
        )

        response = self.client.post(
            "/api/checkout/",
            self.checkout_data(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            Order.objects.filter(
                user=self.user
            ).exists()
        )

    def test_checkout_creates_order_and_reduces_stock(self):
        cart = Cart.objects.create(
            user=self.user
        )

        CartItem.objects.create(
            cart=cart,
            book=self.book,
            quantity=2,
        )

        response = self.client.post(
            "/api/checkout/",
            self.checkout_data(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        order = Order.objects.get(
            user=self.user
        )

        self.assertEqual(
            order.status,
            "pending",
        )

        self.assertEqual(
            order.payment_status,
            "unpaid",
        )

        self.assertEqual(
            order.items.count(),
            1,
        )

        order_item = OrderItem.objects.get(
            order=order
        )

        self.assertEqual(
            order_item.quantity,
            2,
        )

        self.assertEqual(
            order_item.unit_price,
            Decimal("12.50"),
        )

        self.book.refresh_from_db()

        self.assertEqual(
            self.book.stock,
            3,
        )

        cart.refresh_from_db()

        self.assertFalse(
            cart.items.exists()
        )

        self.assertEqual(
            str(response.data["total_price"]),
            "25.00",
        )

    def test_checkout_ignores_client_price_and_payment_status(self):
        cart = Cart.objects.create(
            user=self.user
        )

        CartItem.objects.create(
            cart=cart,
            book=self.book,
            quantity=1,
        )

        data = self.checkout_data()

        # These fields must not control the created order.
        data.update({
            "price": "0.01",
            "total_price": "0.01",
            "payment_status": "paid",
            "status": "confirmed",
            "user": self.other_user.pk,
        })

        response = self.client.post(
            "/api/checkout/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        order = Order.objects.get(
            user=self.user
        )

        self.assertNotEqual(
            order.user_id,
            self.other_user.pk,
        )

        self.assertEqual(
            order.status,
            "pending",
        )

        self.assertEqual(
            order.payment_status,
            "unpaid",
        )

        self.assertEqual(
            order.total_price,
            Decimal("12.50"),
        )

    def test_insufficient_stock_does_not_create_order(self):
        cart = Cart.objects.create(
            user=self.user
        )

        CartItem.objects.create(
            cart=cart,
            book=self.book,
            quantity=6,
        )

        response = self.client.post(
            "/api/checkout/",
            self.checkout_data(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            Order.objects.filter(
                user=self.user
            ).exists()
        )

        self.book.refresh_from_db()

        self.assertEqual(
            self.book.stock,
            5,
        )

        cart.refresh_from_db()

        self.assertTrue(
            cart.items.exists()
        )

    def test_customer_cannot_view_another_users_order(self):
        order = Order.objects.create(
            user=self.other_user,
            status="pending",
        )

        response = self.client.get(
            f"/api/orders/{order.pk}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_customer_cannot_cancel_another_users_order(self):
        order = Order.objects.create(
            user=self.other_user,
            status="pending",
        )

        response = self.client.post(
            f"/api/orders/{order.pk}/cancel/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_customer_cannot_pay_for_another_users_order(self):
        order = Order.objects.create(
            user=self.other_user,
            status="pending",
        )

        response = self.client.post(
            f"/api/orders/{order.pk}/simulate-payment/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        order.refresh_from_db()

        self.assertEqual(
            order.payment_status,
            "unpaid",
        )

    def test_demo_payment_can_only_succeed_once(self):
        order = Order.objects.create(
            user=self.user,
            status="pending",
        )

        first_response = self.client.post(
            f"/api/orders/{order.pk}/simulate-payment/"
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        order.refresh_from_db()

        self.assertEqual(
            order.payment_status,
            "paid",
        )

        self.assertEqual(
            order.status,
            "confirmed",
        )

        second_response = self.client.post(
            f"/api/orders/{order.pk}/simulate-payment/"
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_cannot_view_another_users_address(self):
        address = UserAddress.objects.create(
            user=self.other_user,
            label="Private",
            recipient_first_name="Other",
            recipient_last_name="Customer",
            phone_number="09111111111",
            city="Tehran",
            postal_code="1111111111",
            address_line="Private address",
            is_default=True,
        )

        response = self.client.get(
            f"/api/addresses/{address.pk}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_address_list_only_returns_current_users_addresses(self):
        own_address = UserAddress.objects.create(
            user=self.user,
            label="Home",
            recipient_first_name="Test",
            recipient_last_name="Customer",
            phone_number="09123456789",
            city="Tehran",
            postal_code="1234567890",
            address_line="My address",
            is_default=True,
        )

        UserAddress.objects.create(
            user=self.other_user,
            label="Private",
            recipient_first_name="Other",
            recipient_last_name="Customer",
            phone_number="09111111111",
            city="Tehran",
            postal_code="1111111111",
            address_line="Another user's address",
            is_default=True,
        )

        response = self.client.get(
            "/api/addresses/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            item["id"] for item in response.data
        }

        self.assertEqual(
            returned_ids,
            {own_address.pk},
        )

    def test_customer_cannot_modify_another_users_address(self):
        address = UserAddress.objects.create(
            user=self.other_user,
            label="Private",
            recipient_first_name="Other",
            recipient_last_name="Customer",
            phone_number="09111111111",
            city="Tehran",
            postal_code="1111111111",
            address_line="Private address",
            is_default=True,
        )

        response = self.client.patch(
            f"/api/addresses/{address.pk}/",
            {"city": "Another City"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        address.refresh_from_db()

        self.assertEqual(
            address.city,
            "Tehran",
        )

    def test_customer_cannot_delete_another_users_address(self):
        address = UserAddress.objects.create(
            user=self.other_user,
            label="Private",
            recipient_first_name="Other",
            recipient_last_name="Customer",
            phone_number="09111111111",
            city="Tehran",
            postal_code="1111111111",
            address_line="Private address",
            is_default=True,
        )

        response = self.client.delete(
            f"/api/addresses/{address.pk}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertTrue(
            UserAddress.objects.filter(
                pk=address.pk
            ).exists()
        )
