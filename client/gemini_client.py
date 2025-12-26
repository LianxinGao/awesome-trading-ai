import asyncio
import os
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
from dotenv import load_dotenv
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入common模块
from common import tg_tools

load_dotenv()

prompt = """
你是一名精通阿尔布鲁克斯价格行为的短线交易员，请基于图上信息，基于价格行为进行市场分析并作出是否交易的决策。

# 图表解释
- 红色为跌，蓝色为涨

# 要求
1. 盈亏比合理
2. 要有信号K支持交易，不允许盲目入场

# 输出
1. price_action_summary: 价格行为分析
2. next_kline_observation_target: 下一根K线的观察目标
3. direction: 等待/做多/做空
4. entry_price: 入场价
5. take_profit_price: 止盈价
6. stop_loss_price: 止损价

若direction为等待，则4～6为空字符串即可。
"""


class AiResponse(BaseModel):
    price_action_summary: str = Field(description="价格行为总结")
    next_kline_observation_target: str = Field(default='', description="下一K线的观察目标")
    direction: Literal['等待', "做多", "做空"] = Field(description="多空方向")
    entry_price: str = Field(default="", description="入场价格")
    take_profit_price: str = Field(default="", description="止盈价格")
    stop_loss_price: str = Field(default="", description="止损价格")


# 构建正确的图片路径
image_path = Path(__file__).parent / "../visual/btc_kline_chart.png"

if not image_path.exists():
    # 如果相对路径不存在，尝试从项目根目录开始的路径
    image_path = Path(__file__).parent.parent / "visual/btc_kline_chart.png"

if not image_path.exists():
    raise FileNotFoundError(f"btc_kline_chart.png not found at {image_path}")

with open(image_path, 'rb') as f:
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
result = recipe.model_dump_json(indent=4, ensure_ascii=False)
final = asyncio.run(tg_tools._tg_bot_http_post(result))
