from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Type, TypeVar
from dotenv import load_dotenv

load_dotenv()

T = TypeVar('T', bound=BaseModel)

async def request_ai(prompt: str, image_bytes: bytes, response_model: Type[T]) -> str:
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
            prompt
        ],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": response_model.model_json_schema(),
        }
    )
    recipe = response_model.model_validate_json(response.text)
    result = recipe.model_dump_json(indent=4, ensure_ascii=False)
    return result