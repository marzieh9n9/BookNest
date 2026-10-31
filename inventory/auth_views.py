import logging
import secrets
import smtplib

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import (
    authenticate,
    get_user_model,
    password_validation,
)
from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from drf_spectacular.utils import extend_schema, OpenApiResponse

from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from .models import PasswordResetCode


logger = logging.getLogger(__name__)

User = get_user_model()

OTP_VALIDITY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5
RESET_TOKEN_MAX_AGE_SECONDS = 5 * 60

PASSWORD_RESET_TOKEN_SALT = "booknest.password-reset-otp"


# ==================================================
# 1. REGISTRATION
# ==================================================

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This email cannot be used as a username."
            )

        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Passwords do not match."
            })

        temporary_user = User(
            username=attrs["email"],
            email=attrs["email"],
        )

        try:
            password_validation.validate_password(
                attrs["password"],
                user=temporary_user,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError({
                "password": error.messages
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")

        # create_user hashes the password through Django.
        # Never save the raw password directly.
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Account created successfully."
            ),
        },
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "detail": "Registration successful.",
            },
            status=status.HTTP_201_CREATED,
        )


# ==================================================
# 2. LOGIN WITH EMAIL AND PASSWORD
# ==================================================

class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        email = attrs["email"].strip().lower()

        candidate = User.objects.filter(
            email__iexact=email
        ).first()

        if candidate is None:
            raise AuthenticationFailed(
                "Email or password is incorrect."
            )

        user = authenticate(
            request=self.context.get("request"),
            username=candidate.get_username(),
            password=attrs["password"],
        )

        if user is None or not user.is_active:
            raise AuthenticationFailed(
                "Email or password is incorrect."
            )

        attrs["user"] = user

        return attrs


class EmailLoginView(APIView):
    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(
        request=EmailLoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Access and refresh tokens returned."
            ),
        },
    )
    def post(self, request):
        serializer = EmailLoginSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        })


# ==================================================
# 3. REQUEST PASSWORD RESET OTP
# ==================================================

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "A generic response is returned whether "
                    "or not the email belongs to an account."
                )
            ),
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        # Keep the response the same for existing and
        # non-existing accounts to avoid revealing users.
        if user is not None and user.has_usable_password():

            # Generate a cryptographically secure six-digit code.
            otp = f"{secrets.randbelow(1_000_000):06d}"

            with transaction.atomic():

                # Invalidate any previously issued unused codes.
                PasswordResetCode.objects.filter(
                    user=user,
                    is_used=False,
                ).update(is_used=True)

                # Store only the password hash of the OTP.
                reset_code = PasswordResetCode.objects.create(
                    user=user,
                    code_hash=make_password(otp),
                    expires_at=(
                        timezone.now()
                        + timedelta(minutes=OTP_VALIDITY_MINUTES)
                    ),
                )

            subject = "BookNest password reset code"

            message = (
                f"Your BookNest password reset code is: {otp}\n\n"
                f"This code expires in {OTP_VALIDITY_MINUTES} minutes.\n"
                "You can use it only once.\n\n"
                "If you did not request a password reset, "
                "you can ignore this email."
            )

            try:
                sent_count = send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                if sent_count != 1:
                    raise RuntimeError(
                        "The password reset email was not accepted."
                    )

            except (smtplib.SMTPException, OSError, RuntimeError):
                # Do not leave a usable code if delivery failed.
                PasswordResetCode.objects.filter(
                    pk=reset_code.pk
                ).update(is_used=True)

                logger.exception(
                    "BookNest password reset email delivery failed."
                )

        return Response(
            {
                "detail": (
                    "If an active account exists for this email, "
                    "a password reset code has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


# ==================================================
# 4. VERIFY THE SIX-DIGIT OTP
# ==================================================

class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    code = serializers.RegexField(
        regex=r"^\d{6}$",
        min_length=6,
        max_length=6,
        error_messages={
            "invalid": "Enter the six-digit code from your email."
        },
    )


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_verify"

    @extend_schema(
        request=PasswordResetVerifySerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Returns a short-lived reset token "
                    "after successful code verification."
                )
            ),
        },
    )
    def post(self, request):
        serializer = PasswordResetVerifySerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        submitted_code = serializer.validated_data["code"]

        verified_payload = None

        with transaction.atomic():

            user = User.objects.filter(
                email__iexact=email,
                is_active=True,
            ).first()

            reset_code = None

            if user is not None:
                reset_code = (
                    PasswordResetCode.objects
                    .select_for_update()
                    .filter(
                        user=user,
                        is_used=False,
                        verified_at__isnull=True,
                        expires_at__gt=timezone.now(),
                    )
                    .order_by("-created_at")
                    .first()
                )

            if reset_code is not None:

                # Invalidate the record if the attempt limit
                # had already been reached.
                if reset_code.attempts >= MAX_OTP_ATTEMPTS:
                    reset_code.is_used = True

                    reset_code.save(
                        update_fields=["is_used"]
                    )

                elif check_password(
                    submitted_code,
                    reset_code.code_hash,
                ):
                    # A verified code must not be verified again.
                    reset_code.verified_at = timezone.now()

                    reset_code.save(
                        update_fields=["verified_at"]
                    )

                    verified_payload = {
                        "user_id": user.pk,
                        "code_id": reset_code.pk,
                    }

                else:
                    reset_code.attempts += 1

                    if reset_code.attempts >= MAX_OTP_ATTEMPTS:
                        reset_code.is_used = True

                    reset_code.save(
                        update_fields=["attempts", "is_used"]
                    )

        if verified_payload is None:
            raise serializers.ValidationError({
                "code": "The code is invalid or expired."
            })

        # This token proves the OTP was verified.
        # It expires and can be redeemed only once.
        reset_token = signing.dumps(
            verified_payload,
            salt=PASSWORD_RESET_TOKEN_SALT,
            compress=True,
        )

        return Response(
            {
                "detail": (
                    "Code verified successfully. "
                    "You can now choose a new password."
                ),
                "reset_token": reset_token,
            },
            status=status.HTTP_200_OK,
        )


# ==================================================
# 5. SET A NEW PASSWORD
# ==================================================

class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    confirm_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        return attrs


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_confirm"

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(
                description="Password changed successfully."
            ),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        reset_token = serializer.validated_data["reset_token"]

        # Validate the signed reset token and its five-minute lifetime.
        try:
            payload = signing.loads(
                reset_token,
                salt=PASSWORD_RESET_TOKEN_SALT,
                max_age=RESET_TOKEN_MAX_AGE_SECONDS,
            )
        except (signing.BadSignature, TypeError, ValueError):
            raise serializers.ValidationError({
                "reset_token": (
                    "The reset session is invalid or expired. "
                    "Request a new code."
                )
            })

        if not isinstance(payload, dict):
            raise serializers.ValidationError({
                "reset_token": "Invalid reset session."
            })

        user_id = payload.get("user_id")
        code_id = payload.get("code_id")

        if user_id is None or code_id is None:
            raise serializers.ValidationError({
                "reset_token": "Invalid reset session."
            })

        new_password = serializer.validated_data["new_password"]

        try:
            with transaction.atomic():

                # Lock and validate the exact OTP record which
                # was verified earlier.
                reset_code = (
                    PasswordResetCode.objects
                    .select_for_update()
                    .get(
                        pk=code_id,
                        user_id=user_id,
                        is_used=False,
                        verified_at__isnull=False,
                        expires_at__gt=timezone.now(),
                    )
                )

                user = (
                    User.objects
                    .select_for_update()
                    .get(
                        pk=user_id,
                        is_active=True,
                    )
                )

                # Apply the password validators from settings.py.
                try:
                    password_validation.validate_password(
                        new_password,
                        user=user,
                    )
                except DjangoValidationError as error:
                    raise serializers.ValidationError({
                        "new_password": error.messages
                    })

                # Django hashes the new password.
                user.set_password(new_password)

                user.save(update_fields=["password"])

                # Consume this code so the reset cannot be repeated.
                reset_code.is_used = True

                reset_code.save(
                    update_fields=["is_used"]
                )

                # Also invalidate any other outstanding reset codes.
                PasswordResetCode.objects.filter(
                    user=user,
                    is_used=False,
                ).exclude(
                    pk=reset_code.pk
                ).update(is_used=True)

        except (
            PasswordResetCode.DoesNotExist,
            User.DoesNotExist,
        ):
            raise serializers.ValidationError({
                "reset_token": (
                    "The reset session is invalid, expired, "
                    "or has already been used."
                )
            })

        return Response(
            {
                "detail": (
                    "Password changed successfully. "
                    "You can now log in with your new password."
                )
            },
            status=status.HTTP_200_OK,
        )
