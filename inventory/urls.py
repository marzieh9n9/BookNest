from django.urls import path

from .views import (
    BookListView,
    BookDetailView,
    OrderListView,
    OrderDetailView,
    OrderCancelView,
    CartView,
    CartItemAddView,
    CartItemDetailView,
    CheckoutView,
    DemoPaymentView,
    UserAddressListCreateView,
    UserAddressDetailView,
)

from .auth_views import (
    RegisterView,
    EmailLoginView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
)


urlpatterns = [
    # Books
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

    # Orders
    path(
        "orders/",
        OrderListView.as_view(),
        name="order-list",
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

    # Registration and login
    path(
        "auth/register/",
        RegisterView.as_view(),
        name="auth-register",
    ),
    path(
        "auth/login/",
        EmailLoginView.as_view(),
        name="auth-login",
    ),

    # Password reset using an email OTP
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "auth/password-reset/verify/",
        PasswordResetVerifyView.as_view(),
        name="password-reset-verify",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
        # Shopping cart
    path(
        "cart/",
        CartView.as_view(),
        name="cart",
    ),
    path(
        "cart/items/",
        CartItemAddView.as_view(),
        name="cart-item-add",
    ),
    path(
        "cart/items/<int:pk>/",
        CartItemDetailView.as_view(),
        name="cart-item-detail",
    ),

    path(
    "checkout/",
    CheckoutView.as_view(),
    name="checkout",
    ),

    path(
        "orders/<int:pk>/simulate-payment/",
        DemoPaymentView.as_view(),
        name="simulate-payment",
    ),
    # Customer saved addresses
    path(
        "addresses/",
        UserAddressListCreateView.as_view(),
        name="address-list-create",
    ),
    path(
        "addresses/<int:pk>/",
        UserAddressDetailView.as_view(),
        name="address-detail",
    ),
  
]
