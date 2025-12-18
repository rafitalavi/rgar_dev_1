from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser
from .models import User
from django.shortcuts import get_object_or_404
from .serializers import UserCreateSerializer, UserListSerializer, UserUpdateSerializer , PasswordResetSerializer , UserNotificationSerializer , OwnerChangePasswordSerializer ,UserStatusUpdateSerializer
from permissions_app.services import has_permission
from medical.models import ClinicUser
from core.utils.pagination import StandardResultsSetPagination
from django.core.exceptions import ObjectDoesNotExist
from accounts.services import deactivate_user
#login
class LoginView(APIView):
    authentication_classes = []

    def post(self, request):
        user = User.objects.filter(
            email=request.data.get("email"),
            is_deleted=False
        ).first()

        if not user or not user.check_password(request.data.get("password")):
            return Response(
                {"success": False,
                "message": "Credentials not matched.",
                "errors": None,
                "data": None},
                status=status.HTTP_401_UNAUTHORIZED
            )
        if not user.is_active:
                return Response(
                { "success": False,
                "message": "Account is inactive. Contact administrator.",
                "errors": None,
                "data": None,},
                status=status.HTTP_403_FORBIDDEN
            )
        if user.is_deleted:
            return Response({
                "success": False,
                "message": "Account has been deleted",
                "errors": None,
                "data": None,
            }, status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "profile_pic": user.picture.url if user.picture else None,
            }
        }, status=status.HTTP_200_OK)


#creation        
class CreateUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "user:create"):
            return Response({"detail":"Forbidden"}, status=403)

        s = UserCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"success": True}, status=201)
    
    
# list    
class ListUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "listUser:view"):
            return Response({"detail":"Forbidden"}, status=403)

        qs = User.objects.filter(is_deleted=False)

        search = request.GET.get("search")
        role = request.GET.get("role")
        clinic = request.GET.get("clinic")
        active = request.GET.get("active")

        # user sees only his clinic users (unless owner)
        if request.user.role != "owner":
            my_clinics = ClinicUser.objects.filter(user=request.user).values_list("clinic_id", flat=True)
            qs = qs.filter(clinicuser__clinic_id__in=list(my_clinics))

        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
        if role:
            qs = qs.filter(role=role)
        if active in ["true", "false"]:
            qs = qs.filter(is_active=(active == "true"))
        if clinic:
            qs = qs.filter(clinicuser__clinic_id=clinic)
        qs = qs.distinct().order_by("id")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)

        serializer = UserListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

        # return Response(UserListSerializer(qs.distinct(), many=True).data)



#details
class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not has_permission(request.user, "user:view"):
            return Response(
                {"detail": "Forbidden"},
                status=status.HTTP_403_FORBIDDEN
            )

        user = get_object_or_404(
            User,
            id=user_id,
            is_deleted=False
        )

        # 🔒 Owner → can see everyone
        if request.user.role == "owner":
            pass

        # 🏥 President / Manager → same clinic only
        elif request.user.role in ["president", "manager"]:
            my_clinics = ClinicUser.objects.filter(
                user=request.user
            ).values_list("clinic_id", flat=True)

            target_clinics = ClinicUser.objects.filter(
                user=user,
                clinic_id__in=my_clinics
            ).exists()

            if not target_clinics:
                return Response(
                    {"detail": "Forbidden"},
                    status=status.HTTP_403_FORBIDDEN
                )

        # 👤 Other roles → self only
        else:
            if request.user.id != user.id:
                return Response(
                    {"detail": "Forbidden"},
                    status=status.HTTP_403_FORBIDDEN
                )

        return Response(
            UserListSerializer(user).data,
            status=status.HTTP_200_OK
        )



# update    
class UpdateUserView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    def patch(self, request, user_id):
        if not has_permission(request.user, "user:update"):
            return Response({"detail": "Forbidden"}, status=403)

        user = User.objects.get(id=user_id, is_deleted=False)

        s = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True
        )
        s.is_valid(raise_exception=True)
        s.save()

        return Response(s.data)
#pass word    
class PasswordResetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordResetSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"detail": "Password updated successfully"},
            status=status.HTTP_200_OK
        )
 #notifications off assesment and messege
class UserNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserNotificationSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserNotificationSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
   
    
# delete    

class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        # 1️⃣ Permission check
        if not has_permission(request.user, "user:delete"):
            return Response(
                {
                    "success": False,
                    "message": "You do not have permission to delete users",
                    "errors": None,
                    "data": None,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2️⃣ User existence check
        try:
            user = User.objects.get(id=user_id, is_deleted=False)
        except User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "User not found",
                    "errors": None,
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 3️⃣ Prevent deleting owner
        if user.role == "owner":
            return Response(
                {
                    "success": False,
                    "message": "Owner account cannot be deleted",
                    "errors": None,
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4️⃣ Deactivate user (soft delete + logout)
        deactivate_user(user)

        # 5️⃣ Success response
        return Response(
            {
                "success": True,
                "message": "User deleted successfully",
                "errors": None,
                "data": None,
            },
            status=status.HTTP_200_OK,
        )
    
#owner can change password  view
class OwnerChangeUserPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        # 🔒 Owner only
        if request.user.role != "owner":
            return Response(
                {"message": "Only owner can change passwords"},
                status=status.HTTP_403_FORBIDDEN
            )

        user = get_object_or_404(
            User,
            id=user_id,
            is_deleted=False
        )

        serializer = OwnerChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response(
            {
                "success": True,
                "message": "Password updated successfully",
                "user_id": user.id,
                "email": user.email,
            },
            status=status.HTTP_200_OK
        )
        
        
        
     #blocked user and active    

class UpdateUserStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        if not has_permission(request.user, "user:update"):
            return Response(status=403)

        target = User.objects.filter(id=user_id, is_deleted=False).first()
        if not target:
            return Response(status=404)

        # ❌ Cannot block or deactivate owner
        if target.role == "owner":
            return Response(
                {"detail": "Owner cannot be modified"},
                status=403
            )

        serializer = UserStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(target, field, value)

        target.save(update_fields=serializer.validated_data.keys())
        return Response({"success": True})
