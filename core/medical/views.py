from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from .models import Clinic, ClinicUser
from .serializers import ClinicSerializer
from django.db.models import Count, Q ,Value

from django.db.models.functions import Concat
from accounts.models import User
from permissions_app.services import has_permission
from .services import delete_clinic_and_users
from django.shortcuts import get_object_or_404
class CreateClinicView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "clinic:create"):
           return Response({"detail": "Forbidden"}, status=403)

        serializer = ClinicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            clinic = serializer.save()
        except IntegrityError:
            return Response(
                {"name": ["A clinic with this name already exists."]},
                status=400,
            )

        ClinicUser.objects.create(user=request.user, clinic=clinic)

        return Response(serializer.data, status=201)

class ListClinicView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "clinic:view"):
            return Response({"detail": "Forbidden"}, status=403)

        qs = Clinic.objects.filter(is_deleted=False)

        if request.user.role != "owner":
            qs = qs.filter(clinicuser__user=request.user)

        qs = qs.annotate(
            active_members=Count(
                "clinicuser__user",
                filter=Q(
                    clinicuser__user__is_active=True,
                    clinicuser__user__is_deleted=False
                ),
                distinct=True
            )
        )

        return Response(
            ClinicSerializer(qs.distinct(), many=True).data
        )

class ClinicDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not has_permission(request.user, "clinic:view"):
            return Response(
                {"detail": "Forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        clinic = get_object_or_404(Clinic, pk=pk)
        serializer = ClinicSerializer(clinic)

        return Response(serializer.data, status=status.HTTP_200_OK)


# class UpdateClinicView(APIView):
#     permission_classes = [IsAuthenticated]

#     def patch(self, request, clinic_id):
#         if not has_permission(request.user, "clinic:update"):
#             return Response({"detail":"Forbidden"}, status=403)

#         clinic = Clinic.objects.get(id=clinic_id, is_deleted=False)

#         # must be assigned to clinic (unless owner)
#         if request.user.role != "owner":
#             if not ClinicUser.objects.filter(user=request.user, clinic=clinic).exists():
#                 return Response({"detail":"Forbidden"}, status=403)

#         clinic.name = request.data.get("name", clinic.name)
#         clinic.save()
#         return Response({"success": True})

class UpdateClinicView(APIView):
    permission_classes = [IsAuthenticated]
    print("I am hit")

    def put(self, request, clinic_id):
        if not has_permission(request.user, "clinic:update"):
            return Response({"detail": "Forbidden"}, status=403)

        clinic = get_object_or_404(Clinic, id=clinic_id)

        if request.user.role != "owner":
            if not ClinicUser.objects.filter(user=request.user, clinic=clinic).exists():
                return Response({"detail": "Forbidden"}, status=403)

        serializer = ClinicSerializer(clinic, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"name": ["A clinic with this name already exists 1."]},
                status=400,
            )

        return Response(serializer.data, status=200)

    
class DeleteClinicView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, clinic_id):
        if not has_permission(request.user, "clinic:delete"):
            return Response({"detail":"Forbidden"}, status=403)

        clinic = Clinic.objects.get(id=clinic_id, is_deleted=False)

        # must be assigned (unless owner)
        if request.user.role != "owner":
            if not ClinicUser.objects.filter(user=request.user, clinic=clinic).exists():
                return Response({"detail":"Forbidden"}, status=403)

        delete_clinic_and_users(clinic)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
    
class ChatUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        clinic_id = request.GET.get("clinic_id")
        search = (request.GET.get("search") or "").strip()
        role = request.GET.get("role")
        exclude_ids = request.GET.get("exclude")

        # STEP 1: clinic_id must belong to requester (unless owner)
        if clinic_id and request.user.role != "owner":
            is_member = ClinicUser.objects.filter(
                clinic_id=clinic_id,
                user=request.user
            ).exists()

            if not is_member:
                return Response(
                    {"detail": "Forbidden: not a member of this clinic"},
                    status=403
                )

        # STEP 2: Base queryset (ClinicUser = source of truth)
        qs = ClinicUser.objects.select_related("user", "clinic").filter(
            user__is_active=True,
            user__is_deleted=False,
            user__is_blocked=False,
        )

        # STEP 3: Visibility (shared clinics only)
        if request.user.role != "owner":
            my_clinic_ids = ClinicUser.objects.filter(
                user=request.user
            ).values_list("clinic_id", flat=True)

            qs = qs.filter(clinic_id__in=my_clinic_ids)

        # STEP 4: explicit clinic filter
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)

        # STEP 5: exclude self
        qs = qs.exclude(user=request.user)

        # STEP 6: role filter
        if role:
            qs = qs.filter(user__role=role)

        # STEP 7: full-name search
        if search:
            qs = qs.annotate(
                full_name=Concat(
                    "user__first_name",
                    Value(" "),
                    "user__last_name"
                )
            ).filter(
                Q(full_name__icontains=search) |
                Q(user__email__icontains=search)
            )

        # STEP 8: exclude selected users
        if exclude_ids:
            exclude_list = [
                int(x) for x in exclude_ids.split(",") if x.isdigit()
            ]
            qs = qs.exclude(user_id__in=exclude_list)

        qs = qs.order_by("user__first_name", "user__last_name")

      
        user_map = {}

        for cu in qs:
            user = cu.user

            if user.id not in user_map:
                user_map[user.id] = {
                    "id": user.id,
                    "name": (
                        f"{user.first_name} {user.last_name}".strip()
                        or user.email
                    ),
                    "email": user.email,
                    "role": user.role,
                    "clinics": []
                }

            user_map[user.id]["clinics"].append({
                "id": cu.clinic.id,
                "name": cu.clinic.name
            })

        results = list(user_map.values())
        # 🔹 MY CLINICS (logged-in user)
        if request.user.role == "owner":
            my_clinics_qs = Clinic.objects.filter(is_deleted=False)

        else:
            my_clinics_qs = Clinic.objects.filter(
                clinicuser__user=request.user,
                clinicuser__is_active=True,
              
            ).distinct()

        my_clinics = [
            {
                "id": clinic.id,
                "name": clinic.name
            }
            for clinic in my_clinics_qs
        ]

        return Response(
            {     "my_clinics": my_clinics,
                "success": True,
                "count": len(results),
                "results": results,
              
            },
            status=200
        )
