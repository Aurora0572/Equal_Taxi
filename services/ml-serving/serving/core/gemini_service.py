import google.generativeai as genai
from .utils import get_env  # utils.py가 core 폴더 안에 있다고 가정

# Gemini API Key 설정
GEMINI_API_KEY = get_env("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


async def ask_gemini_model(prompt: str) -> str:
    """
    Gemini 모델을 호출하여 텍스트 응답을 반환
    """
    model = genai.GenerativeModel("gemini-2.5-pro")
    response = model.generate_content(prompt)
    return response.text
