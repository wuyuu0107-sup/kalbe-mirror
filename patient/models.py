from django.db import models

class Patient(models.Model):
    sin = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    subject_initials = models.CharField(max_length=10)
    
    # Demographics
    gender = models.CharField(max_length=10)
    date_of_birth = models.DateField()  # Will need to parse DD/MM/YYYY format
    address = models.CharField(max_length=255)  # Maps to "Adress (Kec.)"
    phone_number = models.CharField(max_length=20)
    age = models.IntegerField()
    
    # Physical Measurements
    height = models.DecimalField(max_digits=5, decimal_places=2)
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    bmi = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Blood Pressure
    systolic = models.IntegerField()
    diastolic = models.IntegerField()
    
    # Lifestyle
    smoking_habit = models.CharField(max_length=20)
    smoker = models.IntegerField()  
    drinking_habit = models.CharField(max_length=20)
    
    # Lab Results
    hemoglobin = models.DecimalField(max_digits=4, decimal_places=2)
    random_blood_glucose = models.DecimalField(max_digits=5, decimal_places=2)
    sgot = models.DecimalField(max_digits=6, decimal_places=2)
    sgpt = models.DecimalField(max_digits=6, decimal_places=2)
    alkaline_phosphatase = models.DecimalField(max_digits=6, decimal_places=2)
    
    def __str__(self):
        return self.subject_initials
