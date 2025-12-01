import os
from io import BytesIO
from django.conf import settings
from django.db import models


class _VirtualStorage:
    """A minimal storage-compatible object used by the virtual file wrapper.

    It intentionally does not perform any filesystem operations. Methods are
    provided so calling code (which expects a Django `storage` object) will
    not error out. Deletion/save are no-ops because actual files are stored
    elsewhere (Supabase) and handled by the project's Supabase helpers.
    """

    def url(self, name):
        # Prefer uploaded_url on the model when available; otherwise build from MEDIA_URL
        if not name:
            raise ValueError("No name provided")
        return settings.MEDIA_URL + name if hasattr(settings, 'MEDIA_URL') else name

    def delete(self, name):
        # no-op: physical media should not be modified by local storage
        return

    def exists(self, name):
        # Always say False to indicate there is no local file
        return False


class VirtualFieldFile:
    """Lightweight file-like wrapper that mimics Django's FieldFile API.

    It reads/writes the filename from/to the model's attribute but does not
    create or access any physical files on disk.
    """

    def __init__(self, instance, field):
        self.instance = instance
        self.field = field

    @property
    def name(self):
        # Read the raw stored value directly, but be defensive:
        stored = self.instance.__dict__.get(self.field.attname, '') or ""
        # If it's already a string/bytes, return it
        if isinstance(stored, (str, bytes)):
            return stored
        # If someone accidentally stored the wrapper itself, avoid recursion and return empty string
        from save_to_database.models import VirtualFieldFile as _VFF  # local import avoids circularity
        if isinstance(stored, _VFF):
            return ""
        # If it's a file-like object that has a name attribute which is a str, use that
        try:
            candidate = getattr(stored, "name", None)
            if isinstance(candidate, (str, bytes)):
                return candidate
        except Exception:
            pass
        # Final fallback to string conversion (non-recursive for plain objects)
        try:
            return str(stored)
        except Exception:
            return ""

    @name.setter
    def name(self, value):
        # Write directly to instance dict to avoid descriptor recursion
        # Ensure stored path uses POSIX separators and begins with the datasets prefix
        if not value:
            self.instance.__dict__[self.field.attname] = ''
            return
        v = value.replace('\\', '/').lstrip('/')
        if not v.startswith('datasets/csvs/'):
            v = f'datasets/csvs/{v}'
        self.instance.__dict__[self.field.attname] = v

    @property
    def path(self):
        # Provide a simulated path (useful when code concatenates MEDIA_ROOT),
        # but do not assert the file exists.
        if not self.name:
            return ""
        media_root = getattr(settings, 'MEDIA_ROOT', '')
        return os.path.join(media_root, self.name) if media_root else self.name

    @property
    def url(self):
        # Prefer uploaded_url stored on the model when present
        uploaded = getattr(self.instance, 'uploaded_url', None)
        if uploaded:
            return uploaded
        # Fallback to MEDIA_URL + name
        if not self.name:
            raise ValueError('No file is associated')
        media_url = getattr(settings, 'MEDIA_URL', '')
        return media_url + self.name if media_url else self.name

    @property
    def size(self):
        # Size is unknown locally; return 0 or cached value if provided
        return self.instance.__dict__.get(f"_{self.field.name}_size", 0)

    def open(self, mode='rb'):
        # There is no local file to open. Return an empty BytesIO to avoid errors
        # in callers that expect a file-like object.
        return BytesIO()

    def delete(self, save=True):
        # No-op: let Supabase helpers manage actual data. Keep DB field cleared.
        self.name = ""
        if save:
            try:
                self.instance.save()
            except Exception:
                pass

    @property
    def storage(self):
        return _VirtualStorage()

    def __str__(self):
        try:
            return self.name or ""
        except Exception:
            return ""

    def __repr__(self):
        return f"<VirtualFieldFile name={self.name!r}>"


class _VirtualFileDescriptor:
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return VirtualFieldFile(instance, self.field)

    def __set__(self, instance, value):
        # Accept a variety of inputs and *always* store a normalized string path
        if value is None:
            instance.__dict__[self.field.attname] = ''
            return

        # If value is the wrapper (VirtualFieldFile) or a file-like object with .name,
        # try to extract the raw name safely:
        raw = None
        # prefer .name if present and is a string/bytes
        if hasattr(value, 'name'):
            try:
                candidate = getattr(value, 'name')
                if isinstance(candidate, (str, bytes)):
                    raw = candidate
                else:
                    # if candidate is not string, convert
                    raw = str(candidate)
            except Exception:
                raw = str(value)
        else:
            raw = str(value)

        v = raw.replace('\\', '/').lstrip('/')
        if v and not v.startswith('datasets/csvs/'):
            v = f'datasets/csvs/{v}'

        # Always store the normalized string
        instance.__dict__[self.field.attname] = v


class VirtualFileField(models.CharField):
    """A CharField that exposes a file-like descriptor on attribute access.

    The actual value stored in the DB is a text path (the same as a FileField
    would store). On access, the descriptor returns a `VirtualFieldFile`
    instance implementing `.name`, `.path`, `.url`, `.size`, and `.storage`.
    """

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        # Attach our descriptor so `instance.<field>` returns the wrapper
        setattr(cls, name, _VirtualFileDescriptor(self))


class CSV(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    # Store the filename/path in the DB but do NOT manage local files.
    file = VirtualFileField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    source_json = models.JSONField(blank=True, null=True)
    record_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    uploaded_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name
