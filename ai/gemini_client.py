import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Type, TypeVar, Dict, Any
from dotenv import load_dotenv

load_dotenv()

T = TypeVar('T', bound=BaseModel)

async def request_ai(prompt: str, image_bytes_list: list[bytes], response_model: Type[T]) -> Dict[Any, Any]:
    image_datas = [types.Part.from_bytes(data=image_bytes, mime_type='image/png') for image_bytes in image_bytes_list]
    contents = image_datas + [prompt]
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": response_model.model_json_schema(),
        }
    )
    recipe = response_model.model_validate_json(response.text)
    # 返回字典格式，便于后续添加字段
    result_dict = recipe.model_dump()
    return result_dict