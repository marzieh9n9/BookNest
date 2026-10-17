from django.test import TestCase

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Book, Category, Order, OrderItem


User = get_user_model()


class BookNestAPITests(APITestCase):

    def setUp(self):
        # Users
        self.user = User.objects.create_user(
            username="normaluser",
            password="Normal12345"
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="Other12345"
        )

        self.admin = User.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            password="Admin12345"
        )

        # Category
        self.category = Category.objects.create(
            name="Programming"
        )

        # Book
        self.book = Book.objects.create(
            title="Django for APIs",
            author="William Vincent",
            price=Decimal("30.00"),
            stock=5,
            category=self.category
        )

        # URLs
        self.book_list_url = reverse("book-list")
        self.order_list_url = reverse("order-list")

    def test_book_list_and_search(self):
        response = self.client.get(
            self.book_list_url,
            {"search": "django"}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.book.id
        )

    def test_pagination(self):
        for number in range(5):
            Book.objects.create(
                title=f"Extra Book {number}",
                author="Test Author",
                price=Decimal("20.00"),
                stock=2,
                category=self.category
            )

        response = self.client.get(self.book_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(response.data["count"], 6)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIsNotNone(response.data["next"])

        second_page = self.client.get(
            self.book_list_url,
            {"page": 2}
        )

        self.assertEqual(
            second_page.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(second_page.data["results"]), 1)

    def test_normal_user_cannot_create_book(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.book_list_url,
            {
                "title": "New Book",
                "author": "Test Author",
                "price": "20.00",
                "stock": 3,
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertFalse(
            Book.objects.filter(title="New Book").exists()
        )

    def test_admin_can_create_book(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.book_list_url,
            {
                "title": "New Book",
                "author": "Test Author",
                "price": "20.00",
                "stock": 3,
                "category": self.category.id,
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertTrue(
            Book.objects.filter(title="New Book").exists()
        )

    def test_jwt_login_and_refresh(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {
                "username": "normaluser",
                "password": "Normal12345",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        access_token = response.data["access"]
        refresh_token = response.data["refresh"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        orders_response = self.client.get(self.order_list_url)

        self.assertEqual(
            orders_response.status_code,
            status.HTTP_200_OK
        )

        refresh_response = self.client.post(
            reverse("token_refresh"),
            {"refresh": refresh_token},
            format="json"
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn("access", refresh_response.data)

    def test_orders_require_authentication(self):
        response = self.client.get(self.order_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_creating_order_decreases_stock(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.order_list_url,
            {
                "items": [
                    {
                        "book": self.book.id,
                        "quantity": 2,
                    }
                ]
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.book.refresh_from_db()

        self.assertEqual(self.book.stock, 3)

        order = Order.objects.get(id=response.data["id"])
        item = OrderItem.objects.get(order=order)

        self.assertEqual(item.unit_price, Decimal("30.00"))
        self.assertEqual(item.line_total, Decimal("60.00"))
        self.assertEqual(order.total_price, Decimal("60.00"))

    def test_order_cannot_exceed_stock(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.order_list_url,
            {
                "items": [
                    {
                        "book": self.book.id,
                        "quantity": 6,
                    }
                ]
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(Order.objects.count(), 0)

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)

    def test_cancelling_order_restores_stock(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.order_list_url,
            {
                "items": [
                    {
                        "book": self.book.id,
                        "quantity": 2,
                    }
                ]
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        order_id = response.data["id"]

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 3)

        cancel_url = reverse(
            "order-cancel",
            kwargs={"pk": order_id}
        )

        cancel_response = self.client.post(
            cancel_url,
            {},
            format="json"
        )

        self.assertEqual(
            cancel_response.status_code,
            status.HTTP_200_OK
        )

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)

        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, "cancelled")

        # Cancelling again must not restore stock twice.
        second_cancel = self.client.post(
            cancel_url,
            {},
            format="json"
        )

        self.assertEqual(
            second_cancel.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)

    def test_user_cannot_view_another_users_order(self):
        order = Order.objects.create(user=self.other_user)

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("order-detail", kwargs={"pk": order.id})
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_duplicate_book_is_rejected_in_same_order(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.order_list_url,
            {
                "items": [
                    {
                        "book": self.book.id,
                        "quantity": 1,
                    },
                    {
                        "book": self.book.id,
                        "quantity": 2,
                    },
                ]
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(Order.objects.count(), 0)

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
