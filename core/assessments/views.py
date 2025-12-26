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
    NotificationSerializer
)
from django.db import transaction
from .utils import flatten_serializer_errors, ok, err
from .services_ai_assesment import generate_questions_for_assessment

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

        # remove non-model fields
        data.pop("count", None)
        data.pop("created_by", None)

        # default end_date = now + 7 days
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
                created_by=request.user,  # ✅ FIX
            )

            # 🔥 GENERATE QUESTIONS IF COUNT PROVIDED
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
        status_value = request.data.get("status")

        if status_value not in ["active", "paused", "closed"]:
            return err("Invalid status")

        if status_value == "active" and not assessment.role:
            return err("Role must be set before starting assessment")

        assessment.status = status_value
        assessment.save()

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

class MyAssessmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assessments = Assessment.objects.filter(
            userassessment__user=request.user,
            status="active",
        ).distinct()

        return ok(
            "My active assessments fetched",
            AssessmentSerializer(assessments, many=True).data,
        )


class SubmitAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, question_id):
        question = get_object_or_404(Question, id=question_id)
        assessment = question.assessment

        if assessment.status != "active":
            return err("Assessment is not active")

        if not UserAssessment.objects.filter(
            user=request.user,
            assessment=assessment
        ).exists():
            return err("Forbidden", status_code=403)

        serializer = AnswerSerializer(data=request.data)
        if not serializer.is_valid():
            msgs = flatten_serializer_errors(serializer.errors)
            return err(msgs[0], serializer.errors)

        Answer.objects.update_or_create(
            user=request.user,
            question=question,
            defaults={"answer_text": serializer.validated_data["answer_text"]},
        )

        return ok("Answer submitted", None, 201)


class SubmitAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, id=assessment_id)

        if assessment.status != "active":
            return err("Assessment is not active")

        ua = UserAssessment.objects.filter(
            user=request.user,
            assessment=assessment
        ).first()

        if not ua:
            return err("Forbidden", status_code=403)

        if ua.status == "completed":
            return err("Assessment already submitted")

        ua.status = "completed"
        ua.submitted_at = timezone.now()
        ua.save(update_fields=["status", "submitted_at"])

        return ok(
            "Assessment submitted successfully",
            {"submitted_at": ua.submitted_at},
            status_code=200,
        )


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



class AIScoreAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assessment_id):
        if not has_permission(request.user, "assessment:score"):
            return err("Forbidden", status_code=403)

        assessment = get_object_or_404(Assessment, id=assessment_id)

        completed_users = UserAssessment.objects.filter(
            assessment=assessment,
            status="completed"
        ).select_related("user")

        results = []

        QUESTIONS_MAX_SCORE = 10  # per question

        for ua in completed_users:
            user = ua.user

            total_score = 0
            max_score = 0
            per_question_scores = []

            questions = Question.objects.filter(assessment=assessment)

            for q in questions:
                max_score += QUESTIONS_MAX_SCORE

                answer = Answer.objects.filter(
                    user=user,
                    question=q
                ).first()

                if not answer:
                    per_question_scores.append({
                        "question_id": q.id,
                        "score": 0,
                    })
                    continue

                # 🧠 AI SCORING STUB (replace later)
                ai_score = 7  # 0–10
                total_score += ai_score

                per_question_scores.append({
                    "question_id": q.id,
                    "score": ai_score,
                })

            # (Optional) save to Score model if you have one
            # Score.objects.update_or_create(...)

            results.append({
                "user_id": user.id,
                "total_score": total_score,
                "max_score": max_score,
                "questions": per_question_scores,
            })

        return ok(
            "AI scoring completed",
            results,
            status_code=200,
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


class AIScoreAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assessment_id):
        if not has_permission(request.user, "assessment:score"):
            return err("Forbidden", status_code=403)

        assessment = get_object_or_404(Assessment, id=assessment_id)

        completed_users = UserAssessment.objects.filter(
            assessment=assessment,
            status="completed"
        ).select_related("user")

        QUESTIONS_MAX_SCORE = 10  # per question

        results = []

        for ua in completed_users:
            user = ua.user

            total_score = 0
            max_score = 0

            questions = Question.objects.filter(assessment=assessment)

            for q in questions:
                max_score += QUESTIONS_MAX_SCORE

                answer = Answer.objects.filter(
                    user=user,
                    question=q
                ).first()

                if not answer:
                    continue  # score 0

                # 🧠 AI SCORING STUB (replace later)
                ai_score = 7  # 0–10
                total_score += ai_score

            # ✅ SAVE SCORE
            Score.objects.update_or_create(
                user=user,
                assessment=assessment,
                defaults={
                    "total_score": total_score,
                    "max_score": max_score,
                },
            )

            results.append({
                "user_id": user.id,
                "total_score": total_score,
                "max_score": max_score,
            })

        return ok(
            "AI scoring completed",
            results,
            status_code=200,
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


class CreatorAssessmentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "assessment:view"):
            return err("Forbidden", status_code=403)

        assessments = (
            Assessment.objects
            .filter(created_by=request.user)
            .annotate(
                total_members=Count("userassessment", distinct=True),
                completed_members=Count(
                    "userassessment",
                    filter=F("userassessment__status") == "completed",
                    distinct=True,
                ),
            )
            .order_by("-created_at")
        )

        data = []

        for assessment in assessments:
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

            data.append({
                "assessment_id": assessment.id,
                "title": assessment.title,
                "role": assessment.role,
                "status": assessment.status,
                "due_date": assessment.end_date.date(),
                "completed_members": assessment.completed_members,
                "total_members": assessment.total_members,
                "average_score": round(avg_percentage),
            })

        return ok("Assessment history fetched", data)
    
    
class ReviewAssessmentResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id):
        if not has_permission(request.user, "assessment:view"):
            return err("Forbidden", status_code=403)

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
