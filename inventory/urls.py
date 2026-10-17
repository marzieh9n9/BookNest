from django.urls import path
from .views import (BookListView,BookDetailView,OrderListView,OrderDetailView,OrderCancelView,)


urlpatterns = [
    path(
        "books/",
        BookListView.as_view(),
        name="book-list",
    ),
    path(
        "books/<int:pk>/",
        BookDetailView.as_view(),
        name="book-detail",
    ),
    path(
    "orders/",
    OrderListView.as_view(),
    name="order-list"
    ),
    path(
    "orders/<int:pk>/",
    OrderDetailView.as_view(),
    name="order-detail",
    ),
    path(
        "orders/<int:pk>/cancel/",
        OrderCancelView.as_view(),
        name="order-cancel",
    ),
]

