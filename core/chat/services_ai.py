def build_ai_prompt(user, message_text: str) -> str:
    # your role-based behavior comes from DB (user.role)
    return f"You are an assistant for role={user.role}, level={getattr(user,'knowledge_level',0)}. Message: {message_text}"

def generate_ai_reply(prompt: str) -> str:
    # Replace later with OpenAI/local LLM call
    return f"(AI) {prompt[:180]}"
