from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from .models import Clinic, ClinicUser
from .serializers import ClinicSerializer
from django.db.models import Count, Q
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
    
    
    
class ClinicUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, clinic_id):
        # 🔐 Permission: owner OR clinic member with clinic:view
        if request.user.role != "owner":
            if not has_permission(request.user, "clinic:view"):
                return Response({"detail": "Forbidden"}, status=403)

            if not ClinicUser.objects.filter(
                clinic_id=clinic_id,
                user=request.user
            ).exists():
                return Response({"detail": "Forbidden"}, status=403)

        qs = (
            ClinicUser.objects
            .filter(
                clinic_id=clinic_id,
                user__is_active=True,
                user__is_deleted=False,
                user__is_blocked=False,
            )
            .select_related("user")
        )

        # 🔹 role-based filtering
        role = request.GET.get("role")
        if role:
            qs = qs.filter(user__role=role)

        # 🔹 search (name/email)
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )

        # 🔹 exclude selected users
        exclude_ids = request.GET.get("exclude")
        if exclude_ids:
            qs = qs.exclude(user_id__in=exclude_ids.split(","))

        qs = qs.order_by("user__first_name", "user__last_name")

        results = [
            {
                "id": cu.user.id,
                "first_name": cu.user.first_name,
                "last_name": cu.user.last_name,
                "email": cu.user.email,
                "role": cu.user.role,
            }
            for cu in qs
        ]

        # 🔹 optional owner injection
        if request.GET.get("include_owner") == "1":
            owner = User.objects.filter(
                role="owner",
                is_active=True,
                is_deleted=False
            ).first()
            if owner:
                results.insert(0, {
                    "id": owner.id,
                    "first_name": owner.first_name,
                    "last_name": owner.last_name,
                    "email": owner.email,
                    "role": owner.role,
                    "read_only": True
                })

        return Response({
            "clinic_id": clinic_id,
            "count": len(results),
            "results": results
        })
