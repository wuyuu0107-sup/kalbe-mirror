from django.db import models

# Temporary database models for Document and Patient
class Document(models.Model):
    pass

class Patient(models.Model):
    name = models.CharField(max_length=255)
    pass

class Annotation(models.Model):
    document = models.ForeignKey(Document, related_name='annotations', on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, related_name='annotations', on_delete=models.CASCADE)
    drawing_data = models.JSONField()  # Store drawing as JSON (SVG, coordinates, etc.)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # def __str__(self):
    #     return f"Annotation for {self.patient.name} in {self.document.title}"
