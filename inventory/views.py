from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiParameter,
    OpenApiTypes,
)

from .models import (Book, Order, OrderItem, Cart, CartItem,UserAddress,)

from .serializers import (
    BookSerializer,
    OrderSerializer,
    CartSerializer,
    AddCartItemSerializer,
    UpdateCartItemSerializer,
    CheckoutSerializer,
    UserAddressSerializer,
    BookPaginationSerializer,
    DemoPaymentResponseSerializer,
)

from .permissions import IsAdminOrReadOnly





class BookListPagination(PageNumberPagination):
    page_size = 5
    
class BookListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    pagination_class = BookListPagination

    @extend_schema(
    summary="List books",
    description=(
        "Returns a paginated list of books. "
        "Supports search and filtering."
    ),
    parameters=[
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Search by book title or author.",
        ),
        OpenApiParameter(
            name="stock",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Filter by exact stock quantity.",
        ),
        OpenApiParameter(
            name="price",
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
            description="Filter by exact book price.",
        ),
        OpenApiParameter(
            name="category",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Filter by category ID.",
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=[
                "price",
                "-price",
                "stock",
                "-stock",
                "title",
                "-title",
            ],
            description="Sort the book list.",
        ),
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Page number.",
        ),
    ],
    responses={
        200: BookPaginationSerializer,
    },
    )
    
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


    @extend_schema(
    summary="Create a book",
    description="Creates a new book. Admin access is required.",
    request=BookSerializer,
    responses={
        201: BookSerializer,
        400: OpenApiResponse(
            description="Invalid book data."
        ),
        403: OpenApiResponse(
            description="Admin permission required."
        ),
    },
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
    @extend_schema(
    summary="Retrieve a book",
    responses={
        200: BookSerializer,
        404: OpenApiResponse(
            description="Book not found."
        ),
    },
    )
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
    @extend_schema(
    summary="Partially update a book",
    request=BookSerializer,
    responses={
        200: BookSerializer,
        400: OpenApiResponse(
            description="Invalid book data."
        ),
        403: OpenApiResponse(
            description="Admin permission required."
        ),
    },
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
    @extend_schema(
    summary="Delete a book",
    responses={
        204: OpenApiResponse(
            description="Book deleted successfully."
        ),
        403: OpenApiResponse(
            description="Admin permission required."
        ),
        404: OpenApiResponse(
            description="Book not found."
        ),
    },
    )
    def delete(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        book.delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    summary="List my orders",
    description=(
        "Customers can see only their own orders. "
        "Staff users can see all orders."
    ),
    responses={
        200: OrderSerializer(many=True),
    },
    )
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
    @extend_schema(
    summary="Retrieve an order",
    description=(
        "Customers can retrieve only their own orders. "
        "Staff users can retrieve all orders."
    ),
    responses={
        200: OrderSerializer,
        404: OpenApiResponse(
            description="Order not found."
        ),
    },
    )
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
    @extend_schema(
    summary="Cancel an order",
    description=(
        "Cancels a pending order and restores "
        "the reserved book quantities to stock."
    ),
    responses={
        200: OrderSerializer,
        400: OpenApiResponse(
            description="Only pending orders can be cancelled."
        ),
        404: OpenApiResponse(
            description="Order not found."
        ),
    },
    )
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
    @extend_schema(
    summary="Retrieve shopping cart",
    description="Returns the authenticated user's shopping cart.",
    responses={
        200: CartSerializer,
    },
    )
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(
            user=request.user
        )

        cart = Cart.objects.prefetch_related(
            "items__book"
        ).get(pk=cart.pk)

        serializer = CartSerializer(cart)

        return Response(serializer.data)
    @extend_schema(
    summary="Clear shopping cart",
    responses={
        204: OpenApiResponse(
            description="Shopping cart cleared."
        ),
    },
    )
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
    @extend_schema(
    summary="Add a book to cart",
    request=AddCartItemSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(
            description="Invalid quantity or insufficient stock."
        ),
    },
    )
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
    @extend_schema(
    summary="Update cart item quantity",
    request=UpdateCartItemSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(
            description="Invalid quantity or insufficient stock."
        ),
        404: OpenApiResponse(
            description="Cart item not found."
        ),
    },
    )
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
    @extend_schema(
    summary="Remove an item from cart",
    responses={
        204: OpenApiResponse(
            description="Cart item removed."
        ),
        404: OpenApiResponse(
            description="Cart item not found."
        ),
    },
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
    summary="Checkout shopping cart",
    description=(
        "Creates an order from the authenticated user's cart. "
        "Validates current stock and calculates prices on the server. "
        "The cart is cleared after successful order creation. "
        "Payment remains unpaid until the demo payment endpoint is used."
    ),
    request=CheckoutSerializer,
    responses={
        201: OrderSerializer,
        400: OpenApiResponse(
            description="Cart is empty or stock is insufficient."
        ),
        401: OpenApiResponse(
            description="Authentication required."
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
    summary="Simulate order payment",
    description=(
        "Marks an eligible pending order as paid for demonstration "
        "purposes only. No real money is charged."
    ),
    responses={
        200: DemoPaymentResponseSerializer,
        400: OpenApiResponse(
            description="Order cannot be paid."
        ),
        404: OpenApiResponse(
            description="Order not found."
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
    @extend_schema(
    summary="List my saved addresses",
    responses={
        200: UserAddressSerializer(many=True),
    },
    )
    def get(self, request):
        addresses = UserAddress.objects.filter(
            user=request.user
        )

        serializer = UserAddressSerializer(
            addresses,
            many=True,
        )

        return Response(serializer.data)
    @extend_schema(
    summary="Create a saved address",
    request=UserAddressSerializer,
    responses={
        201: UserAddressSerializer,
        400: OpenApiResponse(
            description="Invalid address data."
        ),
    },
    )
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
    @extend_schema(
    summary="Retrieve a saved address",
    responses={
        200: UserAddressSerializer,
        404: OpenApiResponse(
            description="Address not found."
        ),
    },
    )
    def get(self, request, pk):
        address = self.get_object(request, pk)

        serializer = UserAddressSerializer(address)

        return Response(serializer.data)
    @extend_schema(
    summary="Update a saved address",
    request=UserAddressSerializer,
    responses={
        200: UserAddressSerializer,
        400: OpenApiResponse(
            description="Invalid address data."
        ),
        404: OpenApiResponse(
            description="Address not found."
        ),
    },
    )
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
    @extend_schema(
    summary="Delete a saved address",
    responses={
        204: OpenApiResponse(
            description="Address deleted."
        ),
        404: OpenApiResponse(
            description="Address not found."
        ),
    },
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
