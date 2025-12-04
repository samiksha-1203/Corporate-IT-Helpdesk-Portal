# IT Helpdesk Portal

A Django-based IT Helpdesk Portal with role-based access control, ticket management, and a RESTful API.

## Features

- Role-based access control (Project Manager, Support Engineer, Issue Reporter)
- Ticket creation, assignment, and status tracking
- Comment and attachment support
- Email notifications for ticket events
- RESTful API for integration with other systems
- Audit logging for ticket activities

## Setup Instructions

### 1. Create a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Database Setup

```bash
python manage.py migrate
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
python manage.py runserver
```

The application will be available at http://127.0.0.1:8000/

## Running Tests

```bash
python manage.py test ticketsapp
```

## Email Configuration

By default, the application uses the console email backend for development. To switch to SMTP for production:

1. Update `settings.py`:

```python
# Email settings for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-smtp-server.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'helpdesk@example.com'
```

## Database Configuration

The application uses SQLite by default, which is suitable for development. No additional configuration is required.

For production, consider switching to a more robust database like PostgreSQL or MySQL.

## User Roles

- **Project Manager**: Full access to all tickets, can assign tickets to Support Engineers
- **Support Engineer**: Can view and update assigned tickets
- **Issue Reporter**: Can create tickets and view their own tickets

## API Endpoints

- `/api/tickets/` - List and create tickets
- `/api/tickets/<id>/` - Retrieve, update, and delete tickets
- `/api/comments/` - Create comments
- `/api/attachments/` - Upload attachments