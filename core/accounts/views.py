from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser
from .models import User
from .serializers import UserCreateSerializer, UserListSerializer, UserUpdateSerializer
from permissions_app.services import has_permission
from medical.models import ClinicUser
class LoginView(APIView):
    authentication_classes = []

    def post(self, request):
        user = User.objects.filter(
            email=request.data.get("email"),
            is_deleted=False
        ).first()

        if not user or not user.check_password(request.data.get("password")):
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

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
class CreateUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "user:create"):
            return Response({"detail":"Forbidden"}, status=403)

        s = UserCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({"success": True}, status=201)
class ListUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "user:view"):
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

        return Response(UserListSerializer(qs.distinct(), many=True).data)
    
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
class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        if not has_permission(request.user, "user:delete"):
            return Response(
                {"detail": "Forbidden"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            user = User.objects.get(id=user_id, is_deleted=False)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_deleted = True
        user.is_active = False
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)