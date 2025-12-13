from django.db import models

# Create your models here.


from django.db import models

class SubjectMatters(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title