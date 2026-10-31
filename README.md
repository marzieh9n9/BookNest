\# BookNest — Bookstore Management API



BookNest is a Django REST API project for managing bookstore inventory. It is built with Django REST Framework and includes authentication, permissions, validation, filtering, and API documentation.



\## Features



\- Book management through REST API endpoints

\- Category model and book-category relationship

\- JWT authentication using access and refresh tokens

\- Read access to book endpoints and staff-only write permissions

\- Search by book title and author

\- Filtering, ordering, and pagination

\- Model and serializer validation

\- Interactive API documentation

\- Automated tests

\- Order and order-item data models



\## Technology Stack



\- Python

\- Django

\- Django REST Framework

\- PostgreSQL

\- Simple JWT

\- OpenAPI / Swagger documentation



\## Main Endpoints



| Method | Endpoint | Description |

|---|---|---|

| GET | `/api/books/` | List books |

| POST | `/api/books/` | Create a book (staff permission required) |

| GET | `/api/books/<id>/` | Retrieve a book |

| PUT | `/api/books/<id>/` | Update a book (staff permission required) |

| PATCH | `/api/books/<id>/` | Partially update a book (staff permission required) |

| DELETE | `/api/books/<id>/` | Delete a book (staff permission required) |

| POST | `/api/token/` | Obtain JWT tokens |

| POST | `/api/token/refresh/` | Refresh an access token |



\## API Documentation



When the application is running, open:



`/api/docs/`



The interactive documentation helps developers explore the API endpoints and understand the available operations.



\## Local Setup



1\. Clone the repository.

2\. Create and activate a Python virtual environment.

3\. Install the dependencies from `requirements.txt`.

4\. Create a local `.env` file based on `.env.example`.

5\. Configure the secret key, allowed hosts, debug setting, and database connection in `.env`.

6\. Ensure the configured database is available and apply migrations.

7\. Start the Django development server.



Example commands for Windows PowerShell:



```powershell

python -m venv venv

.\\venv\\Scripts\\Activate.ps1

python -m pip install -r requirements.txt

Copy-Item .env.example .env

notepad .env

python manage.py migrate

python manage.py runserver

```



The database must be configured and available before applying migrations. Do not commit `.env` or any real credentials to version control.



\## Tests



Run the test suite with:



```powershell

python manage.py test inventory

```



\## Project Status



BookNest is a learning and portfolio project focused on backend development, REST API design, authentication, permissions, validation, and testing.

