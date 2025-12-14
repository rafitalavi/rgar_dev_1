from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from .models import SubjectMatters
from .serializers import SubjectMattersSerializer
from permissions_app.services import has_permission

from django.shortcuts import get_object_or_404
# class CreateSubjectView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         if not has_permission(request.user, "subject:create"):
#             return Response({"detail": "Forbidden"}, status=403)

#         serializer = SubjectMattersSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         try:
#             serializer.save()
#         except IntegrityError:
#             return Response(
#                 {"message": ["Subject already exists."]},
#                 status=400,
#             )

#         return Response(serializer.data, status=201)



class CreateSubjectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "subject:create"):
            return Response(
                {"message": ["Forbidden"]},
                status=403
            )

        serializer = SubjectMattersSerializer(data=request.data)

        if not serializer.is_valid():
            # 🔁 Convert field errors to message
            messages = []
            for field_errors in serializer.errors.values():
                messages.extend(field_errors)

            return Response(
                {
                    "message": messages
                },
                status=400
            )

        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {
                    "message": ["Subject already exists."]
                },
                status=400
            )

        return Response(serializer.data, status=201)



class ListSubjectView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "subject:view"):
            return Response(
                {
                    "success": False,
                    "message": "You do not have permission to view subjects",
                    "errors": None,
                    "data": None,
                },
                status=403,
            )

        qs = SubjectMatters.objects.all()
        serializer = SubjectMattersSerializer(qs, many=True)

        return Response(
            {
                "success": True,
                "message": "Subjects fetched successfully",
                "errors": None,
                "data": serializer.data,
            },
            status=200,
        )


class SubjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not has_permission(request.user, "subject:view"):
            return Response(
                {
                    "success": False,
                    "message": "You do not have permission to view subjects",
                    "errors": None,
                    "data": None,
                },
                status=403,
            )

        subject = get_object_or_404(SubjectMatters, pk=pk)
        serializer = SubjectMattersSerializer(subject)
        return Response(serializer.data, status=200)

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






#ok
# class UpdateSubjectView(APIView):
#     permission_classes = [IsAuthenticated]

#     def put(self, request, pk):
#         if not has_permission(request.user, "subject:update"):
#             return Response(
#                 {
#                     "success": False,
#                     "message": "You do not have permission to Update subjects",
#                     "errors": None,
#                     "data": None,
#                 },
#                 status=403,
#             )

#         subject = get_object_or_404(SubjectMatters, pk=pk)

#         serializer = SubjectMattersSerializer(subject, data=request.data)
#         serializer.is_valid(raise_exception=True)

#         try:
#             serializer.save()
#         except IntegrityError:
#             return Response(
#                 {"message": ["Subject name already exists."]},
#                 status=400,
#             )

#         return Response(serializer.data, status=200)

  
class UpdateSubjectView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        # 🔐 Permission check
        if not has_permission(request.user, "subject:update"):
            return Response(
                {
                    "success": False,
                    "message": "You do not have permission to update subjects",
                    "errors": None,
                    "data": None,
                },
                status=403,
            )

        subject = get_object_or_404(SubjectMatters, pk=pk)

        serializer = SubjectMattersSerializer(subject, data=request.data)

        if not serializer.is_valid():
            messages = []
            for errs in serializer.errors.values():
                messages.extend(errs)

            return Response(
                {
                    "success": False,
                    "message": messages[0],
                    "errors": serializer.errors,
                    "data": None,
                },
                status=400,
            )

        
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {
                    "success": False,
                    "message": "Subject name already exists.",
                    "errors": None,
                    "data": None,
                },
                status=400,
            )

       
        return Response(
            {
                "success": True,
                "message": "Subject updated successfully",
                "errors": None,
                "data": serializer.data,
            },
            status=200,
        )
  
    
class DeleteSubjectView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not has_permission(request.user, "subject:delete"):
            return Response({"detail": "Forbidden"}, status=403)

        subject = get_object_or_404(SubjectMatters, pk=pk)
        subject.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
