from .settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",  
    }
}

print(">>> USING TEST_SETTINGS (SQLite) <<<")
print(DATABASES)