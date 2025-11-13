# To run all tests:
# coverage run --source=. manage.py test --settings=kalbe_be.test_settings

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",  
    }
}

print(">>> USING TEST_SETTINGS (SQLite) <<<")
print(DATABASES)