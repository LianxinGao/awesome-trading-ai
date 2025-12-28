import asyncio
from ai.gemini_client import request_ai
from ai.models import TradingRangeResponse, TrendResponse
from ai.prompts import trend_prompts, trading_range_prompt
from visual.draw_klines import plot_candlestick
from visual.prepare_draw_data import get_kline_with_ema
import matplotlib.pyplot as plt
import io
from common import tg_tools
import json
from coin_configs import coin_configs


async def run_inst(inst_id: str, interval: int, limit: int, precision: int):
    klines = await get_kline_with_ema(inst_id, interval, limit, precision)
    markers = [
        # {'timestamp': '2025-12-26 15:45:00', 'text': 'latest kline'},
    ]
    fig, ax = plot_candlestick(klines, title=f"{inst_id} 15-min Candlestick Chart", markers=markers)
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)

    # 获取图像字节数据
    img_buffer.seek(0)  # 移动到缓冲区开头
    image_bytes = img_buffer.getvalue()

    tr_task = request_ai(trading_range_prompt, image_bytes, TradingRangeResponse)
    tend_task = request_ai(trend_prompts, image_bytes, TrendResponse)

    tr_result, tend_result = await asyncio.gather(tr_task, tend_task)

    tr_result['ai_type'] = 'TRADING_RANGE'
    tend_result['ai_type'] = 'TREND'

    tr_response = json.dumps(tr_result, indent=2, ensure_ascii=False)
    tend_response = json.dumps(tend_result, indent=2, ensure_ascii=False)
    # 使用 json.dumps 格式化输出
    print(tr_response)
    print("===================")
    print(tend_response)


    if tr_result['direction'] != '等待':
        await tg_tools.tg_bot_http_post(tr_result)

    if tend_result['direction'] != '等待':
        await tg_tools.tg_bot_http_post(tend_result)

async def run_workflow():
    tasks = []
    for coin_config in coin_configs:
        task = run_inst(coin_config['inst_id'], coin_config['interval'], coin_config['limit'], coin_config['precision'])
        tasks.append(task)

    await asyncio.gather(*tasks)

