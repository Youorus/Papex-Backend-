from django.conf import settings
from google import genai


def ask_gemini(prompt: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY manquante dans les variables d'environnement.")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    return response.text or ""