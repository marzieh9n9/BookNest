from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Book, Order
from .serializers import (BookSerializer,OrderSerializer,)
from .permissions import IsAdminOrReadOnly
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from django.db import transaction


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
            context={"request": request}
        )

        return Response(serializer.data)

    def post(self, request):
        serializer = OrderSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            order = serializer.save()

            return Response(
                OrderSerializer(
                    order,
                    context={"request": request}
                ).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        orders = Order.objects.prefetch_related("items__book")

        if not request.user.is_staff:
            orders = orders.filter(user=request.user)

        order = get_object_or_404(orders, pk=pk)

        serializer = OrderSerializer(
            order,
            context={"request": request}
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



