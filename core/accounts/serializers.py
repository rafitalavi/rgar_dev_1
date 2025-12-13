from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import User
from medical.models import Clinic
from medical.models import ClinicUser

from subject_matters.models import SubjectMatters


# class UserCreateSerializer(serializers.ModelSerializer):
#     employee_id = serializers.CharField(
#         required=False,
#         allow_blank=True,
#         allow_null=True,
#         max_length=50,
#     )
#     email = serializers.EmailField(
#         validators=[UniqueValidator(queryset=User.objects.all())]
#     )
#     password = serializers.CharField(write_only=True)
#     clinic_ids = serializers.ListField(
#         child=serializers.IntegerField(),
#         write_only=True,
#         required=False,
#     )
#     subject_ids = serializers.ListField(
#         child=serializers.IntegerField(),
#         write_only=True,
#         required=False,
#     )
    
#     picture = serializers.ImageField(
#         required=False,
#         allow_null=True
#     )

#     class Meta:
#         model = User
#         fields = (
#             "employee_id",
#             "email",
#             "first_name",
#             "last_name",
#             "role",
#             "password",
#             "clinic_ids",
#             "subject_ids",
#             "picture",
#         )

#     def validate_employee_id(self, value):
#         if not value:
#             return None

#         value = value.strip()
#         if User.objects.filter(employee_id=value).exists():
#             raise serializers.ValidationError(
#                 "Employee ID already exists"
#             )
#         return value

#     def create(self, validated_data):
#         clinic_ids = validated_data.pop("clinic_ids", [])
#         subject_ids = validated_data.pop("subject_ids", [])
#         password = validated_data.pop("password")

#         user = User.objects.create_user(
#             password=password,
#             **validated_data
#         )

#         if clinic_ids:
#             ClinicUser.objects.bulk_create(
#                 [
#                     ClinicUser(user=user, clinic_id=cid)
#                     for cid in clinic_ids
#                 ]
#             )

#         if subject_ids:
#             user.subject_matters.set(subject_ids)

#         return user

class UserCreateSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=50,
    )

    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.filter(is_deleted=False))]
    )

    password = serializers.CharField(write_only=True)

    clinic_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    subject_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    picture = serializers.ImageField(
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = (
            "employee_id",
            "email",
            "first_name",
            "last_name",
            "role",
            "password",
            "clinic_ids",
            "subject_ids",
            "picture",
            "knowledge_level",
        )

    # ✅ EMPLOYEE ID CHECK
    def validate_employee_id(self, value):
        if not value:
            return None

        value = value.strip()
        if User.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError(
                "Employee ID already exists"
            )
        return value

    # ✅ FIRST & GLOBAL VALIDATION (CLINICS FIRST)
    def validate(self, attrs):
        role = attrs.get("role")
        clinic_ids = attrs.get("clinic_ids", [])

        # ---- clinics required for non-owner ----
        if role != "owner" and not clinic_ids:
            raise serializers.ValidationError({
                "clinic_ids": "Clinics are required for non-owner users."
            })

        # ---- validate clinic IDs ----
        if clinic_ids:
            existing = set(
                Clinic.objects.filter(id__in=clinic_ids)
                .values_list("id", flat=True)
            )
            missing = set(clinic_ids) - existing
            if missing:
                raise serializers.ValidationError({
                    "clinic_ids": f"Invalid clinic IDs: {list(missing)}"
                })

        # ---- validate subject IDs (optional) ----
        subject_ids = attrs.get("subject_ids", [])
        if subject_ids:
            existing = set(
                SubjectMatters.objects.filter(id__in=subject_ids)
                .values_list("id", flat=True)
            )
            missing = set(subject_ids) - existing
            if missing:
                raise serializers.ValidationError({
                    "subject_ids": f"Invalid subject IDs: {list(missing)}"
                })

        return attrs

    def create(self, validated_data):
        clinic_ids = validated_data.pop("clinic_ids", [])
        subject_ids = validated_data.pop("subject_ids", [])
        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        if clinic_ids:
            ClinicUser.objects.bulk_create(
                [
                    ClinicUser(user=user, clinic_id=cid)
                    for cid in clinic_ids
                ]
            )

        if subject_ids:
            user.subject_matters.set(subject_ids)

        return user


class UserListSerializer(serializers.ModelSerializer):
    clinics = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id","email","first_name","last_name","role","is_active","clinics" ,"picture" ,"subject_matters","employee_id", "knowledge_level")

    def get_clinics(self, obj):
        return list(obj.clinicuser_set.values_list("clinic__name", flat=True))

class UserUpdateSerializer(serializers.ModelSerializer):
    clinic_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    clinics = serializers.SerializerMethodField(read_only=True)
    subjects = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "employee_id",
            "picture",
            "clinics",
            "subjects",
            "clinic_ids",
            "subject_ids",
            "knowledge_level",
        )

    def get_clinics(self, obj):
            return list(
            obj.clinicuser_set
            .select_related("clinic")
            .values_list("clinic__name", flat=True)
        )

    def get_subjects(self, obj):
        return list(
            obj.subject_matters.values_list("title", flat=True)
        )

    def validate(self, attrs):
        if "clinic_ids" in attrs:
            existing = set(
                Clinic.objects.filter(id__in=attrs["clinic_ids"])
                .values_list("id", flat=True)
            )
            missing = set(attrs["clinic_ids"]) - existing
            if missing:
                raise serializers.ValidationError(
                    {"clinic_ids": f"Invalid clinic IDs: {list(missing)}"}
                )

        if "subject_ids" in attrs:
            existing = set(
                SubjectMatters.objects.filter(id__in=attrs["subject_ids"])
                .values_list("id", flat=True)
            )
            missing = set(attrs["subject_ids"]) - existing
            if missing:
                raise serializers.ValidationError(
                    {"subject_ids": f"Invalid subject IDs: {list(missing)}"}
                )

        return attrs

    def update(self, instance, validated_data):
        clinic_ids = validated_data.pop("clinic_ids", None)
        subject_ids = validated_data.pop("subject_ids", None)

        instance = super().update(instance, validated_data)

        if clinic_ids is not None:
            instance.clinicuser_set.all().delete()

            ClinicUser.objects.bulk_create(
                [
                    ClinicUser(user=instance, clinic_id=cid)
                    for cid in clinic_ids
                ]
            )

        if subject_ids is not None:
            instance.subject_matters.set(subject_ids)

        return instance

