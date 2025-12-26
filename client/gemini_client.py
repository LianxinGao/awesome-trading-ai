from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal

from dotenv import load_dotenv
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

prompt = "你是一名精通阿尔布鲁克斯价格行为的短线交易员，你倾向于做盈亏比合理且具有较高一些胜率的交易。请基于当前已走完的K线分析市场行情，并给出下一根K线出现时的交易建议，若下一根K线不入场，则给出观测目标是什么，入场价和止盈止损为空。若入场，采用突破单的方式入场，并给出入场价与止盈止损"


class AiResponse(BaseModel):
    price_action_summary: str = Field(description="价格行为总结")
    next_kline_observation_target: str = Field(default='', description="下一K线的观察目标")
    direction: Literal['等待', "做多", "做空"] = Field(description="多空方向")
    entry_price: str = Field(default="", description="入场价格")
    take_profit_price: str = Field(default="", description="止盈价格")
    stop_loss_price: str = Field(default="", description="止损价格")


with open('../visual/btc_kline_chart.png', 'rb') as f:
    image_bytes = f.read()

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
        prompt
    ],
    config={
        "response_mime_type": "application/json",
        "response_json_schema": AiResponse.model_json_schema(),
    }
)

recipe = AiResponse.model_validate_json(response.text)
print(recipe.model_dump_json(indent=4, ensure_ascii=False))