from django.db import models

class Patient(models.Model):
    sin = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    subject_initials = models.CharField(max_length=10)
    
    # Demographics
    gender = models.CharField(max_length=10, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    
    # Physical Measurements
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    bmi = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Blood Pressure
    systolic = models.IntegerField(blank=True, null=True)
    diastolic = models.IntegerField(blank=True, null=True)
    
    # Lifestyle
    smoking_habit = models.CharField(max_length=20, blank=True, null=True)
    smoker = models.IntegerField(blank=True, null=True)
    drinking_habit = models.CharField(max_length=20, blank=True, null=True)
    
    # Lab Results
    hemoglobin = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    random_blood_glucose = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    sgot = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    sgpt = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    alkaline_phosphatase = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    
    def __str__(self):
        return self.subject_initials
