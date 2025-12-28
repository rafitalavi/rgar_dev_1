from .models import Assessment
import random
# def generate_questions_for_assessment(
#     assessment: Assessment,
#     count: int,
#     generator,
# ) -> list[str]:
#     result = generator.generate_assessment_from_kb(
#         clinic_id=str(assessment.clinic_id),
#         user_role=assessment.role,
#         num_questions=count,
#     )

#     if result.get("status") != "success":
#         raise ValueError(result.get("message", "AI generation failed"))

#     raw_questions = result["assessment"]["questions"]

#     questions_text = [
#         q["question_text"]
#         for q in raw_questions
#         if isinstance(q, dict) and "question_text" in q
#     ]

#     if len(questions_text) < count:
#         raise ValueError("AI returned insufficient questions")

#     return questions_text[:count]


def generate_questions_for_assessment(assessment, count: int) -> list[str]:
    if count <= 0:
        raise ValueError("count must be positive")

    return [
        f"Demo Question {i}: Explain this topic."
        for i in range(1, count + 1)
    ]

def score_assessment_answers(
    *,
    questions,
    answers,
    role,
):
    scores = {}

    for q in questions:
        q_id = q["id"]
        if q_id in answers:
            scores[q_id] = random.randint(5, 9)  # demo AI score
        else:
            scores[q_id] = 0

    return scores

# from ai_engine.kb_generator import EnhancedKnowledgeBasedAssessmentGenerator
# from ai_engine.healthdesk import healthdesk_ai

# _kb_generator = EnhancedKnowledgeBasedAssessmentGenerator(
#     healthdesk_ai=healthdesk_ai
# )

# def generate_questions_for_assessment(assessment, count: int) -> list[str]:
#     if count <= 0:
#         raise ValueError("count must be positive")

#     result = _kb_generator.generate_assessment_from_kb(
#         clinic_id=str(assessment.clinic_id),
#         user_role=assessment.role,
#         num_questions=count,
#     )

#     if result.get("status") != "success":
#         raise ValueError(result.get("message", "AI generation failed"))

#     raw_questions = result["assessment"]["questions"]

#     # 🔐 BACKEND NORMALIZATION
#     questions_text = [
#         q["question_text"]
#         for q in raw_questions
#         if isinstance(q, dict) and "question_text" in q
#     ]

#     if len(questions_text) < count:
#         raise ValueError("AI returned insufficient questions")

#     return questions_text[:count]
