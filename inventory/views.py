from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import (Book, Order, OrderItem, Cart, CartItem,UserAddress,)

from .serializers import (
    BookSerializer,
    OrderSerializer,
    CartSerializer,
    AddCartItemSerializer,
    UpdateCartItemSerializer,
    CheckoutSerializer,
    UserAddressSerializer,
)

from .permissions import IsAdminOrReadOnly





class BookListPagination(PageNumberPagination):
    page_size = 5
    
class BookListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    pagination_class = BookListPagination

    def get(self, request):
        books = Book.objects.all()

        search = request.query_params.get("search")

        if search:
            books = books.filter(
                title__icontains=search
            ) | books.filter(
                author__icontains=search
            )

        stock = request.query_params.get("stock")

        if stock:
            books = books.filter(stock=stock)

        price = request.query_params.get("price")

        if price:
            books = books.filter(price=price)

        ordering = request.query_params.get("ordering")
        
        category = request.query_params.get("category")
        if category:
            books = books.filter(category_id=category)
    
        allowed_ordering = [
            "price",
            "-price",
            "stock",
            "-stock",
            "title",
            "-title",
        ]

        if ordering in allowed_ordering:
            books = books.order_by(ordering, "id")
        else:
            books = books.order_by("id")

        paginator = self.pagination_class()

        page = paginator.paginate_queryset(
            books,
            request,
            view=self
        )

        serializer = BookSerializer(page, many=True)

        return paginator.get_paginated_response(
            serializer.data
        )

    def post(self, request):
        serializer = BookSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
class BookDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        serializer = BookSerializer(book)
        return Response(serializer.data)

    def put(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        serializer = BookSerializer(book, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        serializer = BookSerializer(
            book,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        book.delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            orders = Order.objects.all()
        else:
            orders = Order.objects.filter(
                user=request.user
            )

        orders = orders.prefetch_related("items__book")

        serializer = OrderSerializer(
            orders,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)



class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        orders = Order.objects.prefetch_related(
            "items__book"
        )

        if not request.user.is_staff:
            orders = orders.filter(
                user=request.user
            )

        order = get_object_or_404(
            orders,
            pk=pk,
        )

        serializer = OrderSerializer(
            order,
            context={"request": request},
        )

        return Response(serializer.data)


class OrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=pk
            )

            # A normal user can only cancel their own order.
            if (
                not request.user.is_staff
                and order.user_id != request.user.id
            ):
                return Response(
                    {"detail": "Order not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            if order.status != "pending":
                return Response(
                    {"detail": "Only pending orders can be cancelled."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            items = list(order.items.all())
            book_ids = sorted({item.book_id for item in items})

            locked_books = {
                book.pk: book
                for book in (
                    Book.objects.select_for_update()
                    .filter(pk__in=book_ids)
                    .order_by("pk")
                )
            }

            for item in items:
                book = locked_books[item.book_id]
                book.stock += item.quantity
                book.save(update_fields=["stock"])

            order.status = "cancelled"
            order.save()

        serializer = OrderSerializer(
            order,
            context={"request": request}
        )

        return Response(serializer.data)



# ==================================================
# Shopping cart views
# ==================================================

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(
            user=request.user
        )

        cart = Cart.objects.prefetch_related(
            "items__book"
        ).get(pk=cart.pk)

        serializer = CartSerializer(cart)

        return Response(serializer.data)

    def delete(self, request):
        cart = Cart.objects.filter(
            user=request.user
        ).first()

        if cart is not None:
            cart.items.all().delete()
            cart.save(update_fields=["updated_at"])

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class CartItemAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddCartItemSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        requested_book = serializer.validated_data["book"]
        requested_quantity = serializer.validated_data["quantity"]

        with transaction.atomic():
            # Lock the book row while checking stock.
            book = get_object_or_404(
                Book.objects.select_for_update(),
                pk=requested_book.pk,
            )

            if book.stock < 1:
                return Response(
                    {
                        "detail": (
                            "This book is currently out of stock."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cart, _ = Cart.objects.get_or_create(
                user=request.user
            )

            item = (
                CartItem.objects.select_for_update()
                .filter(
                    cart=cart,
                    book=book,
                )
                .first()
            )

            new_quantity = requested_quantity

            if item is not None:
                new_quantity += item.quantity

            if new_quantity > book.stock:
                return Response(
                    {
                        "detail": (
                            f"Only {book.stock} copies "
                            "are currently available."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if item is None:
                CartItem.objects.create(
                    cart=cart,
                    book=book,
                    quantity=new_quantity,
                )
            else:
                item.quantity = new_quantity

                item.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

            cart.save(update_fields=["updated_at"])

        cart = Cart.objects.prefetch_related(
            "items__book"
        ).get(pk=cart.pk)

        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_200_OK,
        )


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = UpdateCartItemSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data["quantity"]

        with transaction.atomic():
            # The item must belong to the logged-in user.
            item = get_object_or_404(
                CartItem.objects.select_for_update(),
                pk=pk,
                cart__user=request.user,
            )

            book = get_object_or_404(
                Book.objects.select_for_update(),
                pk=item.book_id,
            )

            if quantity > book.stock:
                return Response(
                    {
                        "detail": (
                            f"Only {book.stock} copies "
                            "are currently available."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            item.quantity = quantity

            item.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )

            cart = item.cart
            cart.save(update_fields=["updated_at"])

        cart = Cart.objects.prefetch_related(
            "items__book"
        ).get(pk=cart.pk)

        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        with transaction.atomic():
            item = get_object_or_404(
                CartItem.objects.select_for_update(),
                pk=pk,
                cart__user=request.user,
            )

            cart_id = item.cart_id

            item.delete()

            cart = Cart.objects.get(pk=cart_id)
            cart.save(update_fields=["updated_at"])

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CheckoutSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(
                description="The cart is empty or stock is insufficient.",
            ),
        },
    )
    def post(self, request):
        checkout_serializer = CheckoutSerializer(
            data=request.data
        )
        checkout_serializer.is_valid(raise_exception=True)

        checkout_data = checkout_serializer.validated_data

        with transaction.atomic():
            # Lock the user's cart first.
            cart = (
                Cart.objects
                .select_for_update()
                .filter(user=request.user)
                .first()
            )

            if cart is None:
                raise ValidationError({
                    "cart": "Your shopping cart is empty."
                })

            # Lock cart rows in a consistent order.
            cart_items = list(
                CartItem.objects
                .select_for_update()
                .filter(cart=cart)
                .order_by("book_id")
            )

            if not cart_items:
                raise ValidationError({
                    "cart": "Your shopping cart is empty."
                })

            book_ids = sorted({
                item.book_id for item in cart_items
            })

            # Lock all relevant books before checking stock.
            locked_books = {
                book.pk: book
                for book in (
                    Book.objects
                    .select_for_update()
                    .filter(pk__in=book_ids)
                    .order_by("pk")
                )
            }

            if len(locked_books) != len(book_ids):
                raise ValidationError({
                    "cart": (
                        "One or more books are no longer available."
                    )
                })

            # Always use current database prices and stock.
            for cart_item in cart_items:
                book = locked_books[cart_item.book_id]

                if cart_item.quantity > book.stock:
                    raise ValidationError({
                        "stock": (
                            f"Not enough stock for '{book.title}'. "
                            f"Available: {book.stock}."
                        )
                    })

            # Create the order with the customer's delivery details.
            order = Order.objects.create(
                user=request.user,
                **checkout_data,
            )

            # Save price snapshots and reduce stock atomically.
            for cart_item in cart_items:
                book = locked_books[cart_item.book_id]

                OrderItem.objects.create(
                    order=order,
                    book=book,
                    quantity=cart_item.quantity,
                    unit_price=book.price,
                )

                book.stock -= cart_item.quantity
                book.save(update_fields=["stock"])

            # Clear the cart only after all order items are saved.
            cart.items.all().delete()
            cart.save(update_fields=["updated_at"])

        order = (
            Order.objects
            .prefetch_related("items__book")
            .get(pk=order.pk)
        )

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class DemoPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description=(
                    "Demo payment recorded successfully. "
                    "No real money was charged."
                ),
            ),
            400: OpenApiResponse(
                description="The order cannot be paid in its current state.",
            ),
            404: OpenApiResponse(
                description="Order not found.",
            ),
        },
    )
    def post(self, request, pk):
        with transaction.atomic():
            # Customers can only pay for their own orders.
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            if order.payment_status == "paid":
                raise ValidationError({
                    "payment": (
                        "This order has already been paid."
                    )
                })

            if order.status != "pending":
                raise ValidationError({
                    "payment": (
                        "Only pending orders can be paid."
                    )
                })

            # This is a DEMO operation, not a real bank payment.
            order.payment_status = "paid"
            order.paid_at = timezone.now()
            order.status = "confirmed"

            order.save(
                update_fields=[
                    "payment_status",
                    "paid_at",
                    "status",
                    "updated_at",
                ]
            )

        return Response(
            {
                "order_id": order.id,
                "payment_status": order.payment_status,
                "order_status": order.status,
                "paid_at": order.paid_at,
                "detail": (
                    "Demo payment succeeded. "
                    "No real money was charged."
                ),
            },
            status=status.HTTP_200_OK,
        )



# ==================================================
# Customer address management
# ==================================================

class UserAddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = UserAddress.objects.filter(
            user=request.user
        )

        serializer = UserAddressSerializer(
            addresses,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request):
        serializer = UserAddressSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            # A user's first address becomes the default.
            has_default = UserAddress.objects.filter(
                user=request.user,
                is_default=True,
            ).exists()

            make_default = (
                serializer.validated_data.get("is_default", False)
                or not has_default
            )

            if make_default:
                UserAddress.objects.filter(
                    user=request.user,
                    is_default=True,
                ).update(is_default=False)

            address = serializer.save(
                user=request.user,
                is_default=make_default,
            )

        return Response(
            UserAddressSerializer(address).data,
            status=status.HTTP_201_CREATED,
        )


class UserAddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(
            UserAddress,
            pk=pk,
            user=request.user,
        )

    def get(self, request, pk):
        address = self.get_object(request, pk)

        serializer = UserAddressSerializer(address)

        return Response(serializer.data)

    def patch(self, request, pk):
        with transaction.atomic():
            # Find and lock only the current user's address.
            address = get_object_or_404(
                UserAddress.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            serializer = UserAddressSerializer(
                address,
                data=request.data,
                partial=True,
            )

            serializer.is_valid(
                raise_exception=True
            )

            make_default = serializer.validated_data.get(
                "is_default",
                address.is_default,
            )

            if make_default:
                UserAddress.objects.filter(
                    user=request.user,
                    is_default=True,
                ).exclude(
                    pk=address.pk
                ).update(is_default=False)

            updated_address = serializer.save()

        return Response(
            UserAddressSerializer(updated_address).data
        )

    def delete(self, request, pk):
        with transaction.atomic():
            address = get_object_or_404(
                UserAddress.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            address.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )