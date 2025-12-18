from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager
from subject_matters.models import SubjectMatters
from django.core.validators import MinValueValidator, MaxValueValidator
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("president", "President"),
        ("manager", "Manager"),
        ("doctor", "Doctor"),
        ("staff", "Staff"),
        ("jr_staff", "Junior Staff"),
    )

    employee_id = models.CharField(
    max_length=50,
    unique=True,
    null=True,
    blank=True,
   
)


    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

   
    picture = models.ImageField(
        upload_to="users/profile_pictures/",
        null=True,
        blank=True,
    )

    subject_matters = models.ManyToManyField(
        SubjectMatters,
        blank=True,
        related_name="users",
    )
    knowledge_level = models.PositiveSmallIntegerField(
    default=0,
    validators=[
        MinValueValidator(0),
        MaxValueValidator(10),
    ],
)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    notify_assessments = models.BooleanField(default=True)
    notify_tagged_messages = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
