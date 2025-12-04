# IT Helpdesk Portal

A simple Django-based helpdesk portal with role-based dashboards for Issue Reporters, Support Engineers, and Project Managers.

## Quickstart (Windows)
- Create and activate a virtual environment:
  - `python -m venv .venv`
  - `.venv\Scripts\activate`
- Install dependencies:
  - `pip install -r helpdesk/requirements.txt`
- Apply migrations:
  - `cd helpdesk`
  - `python manage.py migrate`
- Run the dev server:
  - `python manage.py runserver 127.0.0.1:8000`
- Optional: create an admin user:
  - `python manage.py createsuperuser`

## Project Structure
- `helpdesk/` — Django project root
  - `manage.py` — project management commands
  - `helpdesk/helpdesk/` — settings, URLs, WSGI/ASGI
  - `helpdesk/templates/` — project-level templates (base layout)
  - `helpdesk/ticketsapp/` — main app (models, views, templates, API)
  - `helpdesk/media/` — uploaded attachments (ignored by Git)
  - `helpdesk/db.sqlite3` — local dev database (ignored by Git)
- `.gitignore` — excludes envs, DBs, caches, media uploads
- `myenv/` — local environment (ignored by Git)

## Default URLs
- `http://127.0.0.1:8000/` — Login
- `/register/` — Registration
- `/dashboard/ir/` — Issue Reporter
- `/dashboard/se/` — Support Engineer
- `/dashboard/pm/` — Project Manager

## Notes
- Local DB and media uploads are ignored by `.gitignore` — safe to push.
- SECRET_KEY is currently in `helpdesk/helpdesk/settings.py` for development. For production, move secrets to environment variables.

## License
Add a license file if publishing publicly (MIT recommended).
