from . import settings as base

# copy all UPPERCASE settings from base into this module
for name in dir(base):
    if name.isupper():
        globals()[name] = getattr(base, name)

# override DB for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
