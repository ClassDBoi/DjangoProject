"""Settings for running the test suite without the shared MySQL database.

Uses a throwaway SQLite database, so tests never read or change the shared data
and need no database credentials:

    python manage.py test researchdata --settings=SeniorDesign_AUSME.settings_test
"""
import os

# settings.py requires a secret key; tests only need a placeholder.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")

from .settings import *  # noqa: E402,F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
