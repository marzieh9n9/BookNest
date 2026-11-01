# BookNest — Frontend API Guide

## Project Overview

BookNest is an online bookstore project.

Backend technology:
- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT Authentication

API Base URL (Local Development):

`http://127.0.0.1:8000/api/`

API Documentation:

`http://127.0.0.1:8000/api/docs/`

OpenAPI Schema:

`schema.yml`

## Authentication

Registration:

`POST /auth/register/`

Login:

`POST /auth/login/`

Password Reset Request:

`POST /auth/password-reset/`

Password Reset Verification:

`POST /auth/password-reset/verify/`

Password Reset Confirmation:

`POST /auth/password-reset/confirm/`

For protected endpoints, send the access token:

`Authorization: Bearer ACCESS_TOKEN`

## Books

`GET /books/`

`GET /books/{id}/`

Public book browsing supports pagination, search, filtering and ordering.

Book creation, updating and deletion require administrator access.

## Shopping Cart

`GET /cart/`

`POST /cart/items/`

`PATCH /cart/items/{id}/`

`DELETE /cart/items/{id}/`

`DELETE /cart/`

Each customer can access only their own shopping cart.

## Customer Addresses

`GET /addresses/`

`POST /addresses/`

`PATCH /addresses/{id}/`

`DELETE /addresses/{id}/`

Customers can save and manage their own delivery addresses.

## Orders and Checkout

`POST /checkout/`

`GET /orders/`

`GET /orders/{id}/`

`POST /orders/{id}/cancel/`

New orders must be created through the checkout endpoint.

## Demo Payment

`POST /orders/{id}/simulate-payment/`

Important:

This is a demonstration payment feature only. No real bank payment is processed and no actual money is charged.

## Important Development Notes

- Book prices and stock quantities are controlled by the backend.
- The frontend must not calculate or submit trusted order totals.
- Customers must not access other customers' addresses, carts or orders.
- Protected requests require a valid JWT access token.
- Request and response schemas are documented in Swagger and `schema.yml`.

