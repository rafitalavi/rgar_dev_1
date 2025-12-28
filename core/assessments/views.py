from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Max
from django.db.models import Count, Avg, F, FloatField, ExpressionWrapper
from permissions_app.services import has_permission
from medical.models import ClinicUser
from django.utils import timezone
from datetime import timedelta
from .models import (
    Assessment, Question, Answer,
    UserAssessment, AssesmentNotification ,Score
)
from .serializers import (
    AssessmentSerializer,
    QuestionSerializer,
    AnswerSerializer,
    NotificationSerializer,
    CreatorAssessmentHistorySerializer
)
from django.db import transaction
from .utils import flatten_serializer_errors, ok, err
from .services_ai_assesment import generate_questions_for_assessment , score_assessment_answers

def is_creator(user, assessment):
    return assessment.created_by_id == user.id


class CreateAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "assessment:create"):
            return err("Forbidden", status_code=403)

        clinic_id = request.data.get("clinic")
        role = request.data.get("role")
        count = request.data.get("count")  # optional

        if not clinic_id:
            return err("Clinic is required", {"clinic": ["This field is required."]})

        if not role:
            return err("Role is required", {"role": ["This field is required."]})

        if not ClinicUser.objects.filter(
            user=request.user, clinic_id=clinic_id
        ).exists():
            return err("You are not assigned to this clinic", status_code=403)

        data = request.data.copy()

        data.pop("count", None)
        data.pop("created_by", None)

        
        if not data.get("end_date"):
            data["end_date"] = timezone.now() + timedelta(days=7)

        serializer = AssessmentSerializer(data=data)
        if not serializer.is_valid():
            msgs = flatten_serializer_errors(serializer.errors)
            return err(msgs[0], serializer.errors)

        generated_questions = []

        with transaction.atomic():
            assessment = serializer.save(
                status="draft",
                created_by=request.user, 
            )

        
            if count is not None:
                try:
                    count = int(count)
                    if count <= 0:
                        raise ValueError
                except ValueError:
                    return err("count must be a positive integer")

                questions_text = generate_questions_for_assessment(
                    assessment=assessment,
                    count=count,
                )

                Question.objects.filter(assessment=assessment).delete()

                for idx, text in enumerate(questions_text, start=1):
                    generated_questions.append(
                        Question.objects.create(
                            assessment=assessment,
                            number=idx,
                            text=text,
                        )
                    )

        return ok(
            "Assessment created" + (" and questions generated" if count else ""),
            {
                "assessment": AssessmentSerializer(assessment).data,
                "questions": QuestionSerializer(generated_questions, many=True).data,
            },
            status_code=201,
        )
class AssessmentQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id):
        
        assessment = get_object_or_404(
            Assessment,
            id=assessment_id,
          
        )
        if not (
            assessment.created_by_id == request.user.id
            or request.user.role == "owner"
            or has_permission(request.user, "assessment:view_all")
        ):
            return err("Forbidden", status_code=403)


        questions = Question.objects.filter(
            assessment=assessment
        ).order_by("number")

        return ok(
            "Questions fetched",
            {
                "assessment": {
                    "id": assessment.id,
                    "title": assessment.title,
                    "status": assessment.status,
                    "role": assessment.role,
                    "end_date": assessment.end_date.date(),
                },
                "questions": QuestionSerializer(questions, many=True).data,
            },
        )

class AddQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assessment_id):
        if not has_permission(request.user, "assessment:update"):
            return err("Forbidden", status_code=403)

        assessment = get_object_or_404(Assessment, id=assessment_id)

        if assessment.status != "draft":
            return err("Cannot modify questions after assessment is started")

        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            msgs = flatten_serializer_errors(serializer.errors)
            return err(msgs[0], serializer.errors)

        last_number = (
            Question.objects.filter(assessment=assessment)
            .aggregate(max_num=Max("number"))
            .get("max_num")
        ) or 0

        question = Question.objects.create(
            assessment=assessment,
            number=last_number + 1,
            text=serializer.validated_data["text"],
        )

        return ok(
            "Question added",
            QuestionSerializer(question).data,
            status_code=201,
        )

class DeleteQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not has_permission(request.user, "assessment:update"):
            return err("Forbidden", status_code=403)

        question = get_object_or_404(Question, pk=pk)

        if question.assessment.status != "draft":
            return err("Cannot delete questions after assessment is started")

        question.delete()
        return ok("Question deleted")







class UpdateAssessmentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, assessment_id):
        if not has_permission(request.user, "assessment:update"):
            return err("Forbidden", status_code=403)

        assessment = get_object_or_404(Assessment, id=assessment_id)

        # creator OR owner OR privileged
        if not (
            assessment.created_by_id == request.user.id
            or request.user.role == "owner"
        ):
            return err("Forbidden", status_code=403)

        status_value = request.data.get("status")

        if status_value not in ["active", "paused", "closed"]:
            return err("Invalid status")

        assessment.status = status_value
        assessment.save(update_fields=["status"])

        # Assign users only when activating
        if status_value == "active":
            clinic_users = ClinicUser.objects.filter(
                clinic=assessment.clinic,
                user__role=assessment.role,
            ).select_related("user")

            for cu in clinic_users:
                ua, created = UserAssessment.objects.get_or_create(
                    user=cu.user,
                    assessment=assessment,
                )

                if created:
                    AssesmentNotification.objects.create(
                        user=cu.user,
                        assessment=assessment,
                        title="New Assessment Available",
                        message=f"{assessment.title} is now active. Deadline: {assessment.end_date.date()}",
                    )

        return ok(f"Assessment marked as {status_value}")

from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import time

class UpdateAssessmentEndDateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, assessment_id):
        if not has_permission(request.user, "assessment:update"):
            return err("Forbidden", status_code=403)

        assessment = get_object_or_404(Assessment, id=assessment_id)

        # creator OR owner
        if not (
            assessment.created_by_id == request.user.id
            or request.user.role == "owner"
        ):
            return err("Forbidden", status_code=403)

        end_date_str = request.data.get("end_date")
        if not end_date_str:
            return err("end_date is required (YYYY-MM-DD)")

       
        parsed_date = parse_date(end_date_str)
        if not parsed_date:
            return err("Invalid date format. Use YYYY-MM-DD")

       
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(parsed_date, time(23, 59, 59))
        )

        if end_datetime <= timezone.now():
            return err("end_date must be in the future")

        assessment.end_date = end_datetime
        assessment.save(update_fields=["end_date"])

        return ok(
            "Assessment end date updated",
            {
                "assessment_id": assessment.id,
                "end_date": assessment.end_date.date(),  # return date only
            },
        )


class MyAssessmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assessments = Assessment.objects.filter(
        userassessment__user=request.user,
        status="active",
    ).exclude(
        userassessment__status="completed"
    ).distinct()


        return ok(
            "My active assessments fetched",
            AssessmentSerializer(assessments, many=True).data,
        )



        


class CandidateAssessmentQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, id=assessment_id)

      
        if assessment.status != "active":
            return err("Assessment is not active", status_code=403)
        

       
        if timezone.now() > assessment.end_date:
            return err("Assessment deadline has passed", status_code=403)

        
        if not UserAssessment.objects.filter(
            assessment=assessment,
            user=request.user
        ).exists():
            return err("You are not assigned to this assessment", status_code=403)

        questions = Question.objects.filter(
            assessment=assessment
        ).order_by("number")

        return ok(
            "Questions fetched",
            {
                "assessment": {
                    "id": assessment.id,
                    "title": assessment.title,
                    "end_date": assessment.end_date.date(),
                },
                "questions": [
                    {
                        "id": q.id,
                        "number": q.number,
                        "text": q.text,
                    }
                    for q in questions
                ],
            },
        )


class SubmitAssessmentUnifiedView(APIView):
    permission_classes = [IsAuthenticated]

    QUESTIONS_MAX_SCORE = 10

    def post(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, id=assessment_id)

        # 🔒 must be active
        if assessment.status != "active":
            return err("Assessment is not active")

        # 👤 must be assigned
        ua = UserAssessment.objects.filter(
            assessment=assessment,
            user=request.user
        ).first()

        if not ua:
            return err("Forbidden", status_code=403)

        if ua.status == "completed":
            return err("Assessment already submitted")

        #  deadline handling
        submitted_at = (
            assessment.end_date
            if timezone.now() > assessment.end_date
            else timezone.now()
        )

        #  SAVE ANSWERS (optional)
        answers_payload = request.data.get("answers", [])

        for item in answers_payload:
            question_id = item.get("question_id")
            answer_text = item.get("answer_text")

            if not question_id:
                    continue

            # ❌ skip blank answers
            if answer_text is None or not str(answer_text).strip():
                continue


            question = Question.objects.filter(
                id=question_id,
                assessment=assessment
            ).first()

            if not question:
                continue

            Answer.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={"answer_text": answer_text},
            )

        
        ua.status = "completed"
        ua.submitted_at = submitted_at
        ua.save(update_fields=["status", "submitted_at"])

       
        questions = list(
            Question.objects.filter(assessment=assessment)
        )

        answers_map = {
            a.question_id: a.answer_text
            for a in Answer.objects.filter(
                user=request.user,
                question__assessment=assessment
            )
            if a.answer_text and a.answer_text.strip()
}


        ai_scores = score_assessment_answers(
        questions=[{"id": q.id, "text": q.text} for q in questions],
        answers=answers_map,
        role=assessment.role,
    )

        total_score = sum(ai_scores.values())
        answered_questions_count = len(answers_map)
        max_score = answered_questions_count * self.QUESTIONS_MAX_SCORE

        Score.objects.update_or_create(
            user=request.user,
            assessment=assessment,
            defaults={
                "score": total_score,
                "max_score": max_score,
            },
        )

        return ok(
            "Assessment submitted and scored",
            {
                "assessment_id": assessment.id,
                "submitted_at": submitted_at,
                "total_score": total_score,
                "max_score": max_score,
                "percentage": round(
                    (total_score / max_score) * 100, 2
                ) if max_score else 0,
            },
        )

class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(
            AssesmentNotification, pk=pk, user=request.user
        )
        notification.is_read = True
        notification.save(update_fields=["is_read"])

        return ok("Notification marked as read")


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AssesmentNotification.objects.filter(
            user=request.user
        ).order_by("-created_at")

        return ok(
            "Notifications fetched",
            NotificationSerializer(qs, many=True).data,
        )

class MyAssessmentResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, id=assessment_id)

        # must be assigned
        if not UserAssessment.objects.filter(
            user=request.user,
            assessment=assessment,
            status="completed"
        ).exists():
            return err("Result not available", status_code=403)

        score = Score.objects.filter(
            user=request.user,
            assessment=assessment
        ).first()

        if not score:
            return err("Score not generated yet")

        return ok(
            "Result fetched",
            {
                "assessment_id": assessment.id,
                "total_score": score.total_score,
                "max_score": score.max_score,
            },
            status_code=200,
        )


# class CreatorAssessmentHistoryView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         if not has_permission(request.user, "assessment:view"):
#             return err("Forbidden", status_code=403)

#         assessments = (
#             Assessment.objects
#             .filter(created_by=request.user)
#             .annotate(
#                 total_members=Count("userassessment", distinct=True),
#                 completed_members=Count(
#                     "userassessment",
#                     filter=F("userassessment__status") == "completed",
#                     distinct=True,
#                 ),
#             )
#             .order_by("-created_at")
#         )

#         data = []

#         for assessment in assessments:
#             scores = Score.objects.filter(assessment=assessment)

#             avg_percentage = 0
#             if scores.exists():
#                 avg_percentage = (
#                     scores.aggregate(
#                         avg=Avg(
#                             ExpressionWrapper(
#                                 F("total_score") * 100.0 / F("max_score"),
#                                 output_field=FloatField(),
#                             )
#                         )
#                     )["avg"]
#                     or 0
#                 )

#             data.append({
#                 "assessment_id": assessment.id,
#                 "title": assessment.title,
#                 "role": assessment.role,
#                 "status": assessment.status,
#                 "due_date": assessment.end_date.date(),
#                 "completed_members": assessment.completed_members,
#                 "total_members": assessment.total_members,
#                 "average_score": round(avg_percentage),
#             })

#         return ok("Assessment history fetched", data)
    
from django.db.models import Count, Avg, F, Q, FloatField, ExpressionWrapper
class CreatorAssessmentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "assessment:view"):
            return err("Forbidden", status_code=403)

        qs = Assessment.objects.all()

        # 🔒 Non-owner → only own assessments
        if request.user.role != "owner":
            qs = qs.filter(created_by=request.user)

        qs = (
            qs.annotate(
                total_members=Count("userassessment", distinct=True),
                completed_members=Count(
                    "userassessment",
                    filter=Q(userassessment__status="completed"),
                    distinct=True,
                ),
            )
            .order_by("-created_at")
        )

        serializer = CreatorAssessmentHistorySerializer(qs, many=True)
        return ok("Assessment history fetched", serializer.data)

    
class ReviewAssessmentResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id):
        if not has_permission(request.user, "assessment:view"):
            return err("Forbidden", status_code=403)

        if has_permission(request.user, "assessment:view_all"):
                assessment = get_object_or_404(
                Assessment,
                id=assessment_id
            )
        else:
            assessment = get_object_or_404(
                Assessment,
                id=assessment_id,
                created_by=request.user
            )

        
        total_members = UserAssessment.objects.filter(
            assessment=assessment
        ).count()

        completed_members = UserAssessment.objects.filter(
            assessment=assessment,
            status="completed"
        ).count()

        scores = Score.objects.filter(assessment=assessment)

        avg_percentage = 0
        if scores.exists():
            avg_percentage = (
                scores.aggregate(
                    avg=Avg(
                        ExpressionWrapper(
                            F("total_score") * 100.0 / F("max_score"),
                            output_field=FloatField(),
                        )
                    )
                )["avg"]
                or 0
            )

        # --- PARTICIPANTS ---
        participants = []

        questions_count = Question.objects.filter(
            assessment=assessment
        ).count()

        user_assessments = (
            UserAssessment.objects
            .filter(assessment=assessment, status="completed")
            .select_related("user")
        )

        for idx, ua in enumerate(user_assessments, start=1):
            user = ua.user

            answered_count = Answer.objects.filter(
                user=user,
                question__assessment=assessment
            ).count()

            score = Score.objects.filter(
                user=user,
                assessment=assessment
            ).first()

            percentage = 0
            if score and score.max_score > 0:
                percentage = round((score.total_score / score.max_score) * 100)

            participants.append({
                "id_no": idx,
                "user_id": user.id,
                "user_name": f"{user.first_name} {user.last_name}",
                "clinic": assessment.clinic.name,
                "answered": f"{answered_count}/{questions_count}",
                "score": percentage,
            })

        return ok(
            "Assessment review fetched",
            {
                "assessment": {
                    "id": assessment.id,
                    "title": assessment.title,
                    "role": assessment.role,
                    "status": assessment.status,
                    "due_date": assessment.end_date.date(),
                    "completed_members": completed_members,
                    "total_members": total_members,
                    "average_score": round(avg_percentage),
                },
                "participants": participants,
            },
        )


class ViewUserAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id, user_id):
        if not has_permission(request.user, "assessment:view"):
            return err("Forbidden", status_code=403)

        if has_permission(request.user, "assessment:view_all"):
                assessment = get_object_or_404(
                Assessment,
                id=assessment_id
            )
        else:
            assessment = get_object_or_404(
                Assessment,
                id=assessment_id,
                created_by=request.user
            )


        # ensure user was part of assessment
        ua = UserAssessment.objects.filter(
            assessment=assessment,
            user_id=user_id,
            status="completed"
        ).first()

        if not ua:
            return err("User has not completed this assessment")

        questions = Question.objects.filter(
            assessment=assessment
        ).order_by("number")

        score_obj = Score.objects.filter(
            assessment=assessment,
            user_id=user_id
        ).first()

        QUESTIONS_MAX_SCORE = 10

        answers_data = []

        for q in questions:
            answer = Answer.objects.filter(
                question=q,
                user_id=user_id
            ).first()

            # derive per-question score
            per_q_score = 0
            if answer and score_obj:
                # proportional score assumption
                per_q_score = QUESTIONS_MAX_SCORE if answer else 0

            answers_data.append({
                "question_number": q.number,
                "question_text": q.text,
                "answered": bool(answer),
                "answer_text": answer.answer_text if answer else None,
                "score": per_q_score,
            })

        return ok(
            "User answers fetched",
            {
                "user": {
                    "id": ua.user.id,
                    "name": f"{ua.user.first_name} {ua.user.last_name}",
                },
                "assessment": {
                    "id": assessment.id,
                    "title": assessment.title,
                },
                "answers": answers_data,
            },
        )
