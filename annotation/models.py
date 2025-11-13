from django.db import models
# from django.utils import timezone  # <- you'll need this for the prompt

class Document(models.Model):
    SOURCE_CHOICES = (('json','JSON'), ('pdf','PDF'))
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='json')  # <- add default
    content_url = models.TextField(blank=True, default="")
    payload_json = models.JSONField(blank=True, null=True)
    meta = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # keep as is
    updated_at = models.DateTimeField(auto_now=True)
    payload_json_text = models.TextField(blank=True, null=True)



class Patient(models.Model):
    name = models.CharField(max_length=128)
    external_id = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)  # <-- must be here
    updated_at = models.DateTimeField(auto_now=True)      # <-- and here

    def __str__(self):
        return self.name


class Annotation(models.Model):
    """
    A generic drawing/region annotation for a given (document, patient).
    `drawing_data` is *frontend-defined* (e.g., [{tool:'pen', points:[[x,y],...]}]).
    """
    document = models.ForeignKey(Document, related_name='annotations', on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, related_name='annotations', on_delete=models.CASCADE)
    label = models.CharField(max_length=128, blank=True, default="")  # optional label/tag
    drawing_data = models.JSONField()  # must be a JSON object or list (validated in serializer)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['document', 'patient']),
        ]

class Comment(models.Model):
    document = models.ForeignKey(Document, related_name='comments', on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, related_name='comments', on_delete=models.SET_NULL, null=True, blank=True)
    author = models.CharField(max_length=128, blank=True, default="")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

