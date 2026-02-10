import io
import talib
import json
import asyncio
import time
import matplotlib.pyplot as plt
from client import ok_client
from visual.draw_klines import plot_recent_klines
from ai.gemini_client import request_ai
from pydantic import BaseModel, Field
from typing import Literal
from textwrap import dedent

class MarketCycle(BaseModel):
    id: int = Field(description="图表ID")
    market_cycle: Literal['Trading Range', 'Bull Broad Channel', 'Bear Broad Channel', 'Bull Tight Channel', 'Bear Tight Channel', 'Breakout'] = Field(description="Market cycle type")

SYSTEM_PROMPT = "你精通Al Brooks价格行为理论，请基于给到的图表，判断图表所处的市场周期。"
USER_PROMPT = dedent("""\
请分析图表，分析当前的市场周期，当前图表ID为{chart_id}
market cycle为以下六种之一：
1. Trading Range
2. Bull Broad Channel
3. Bull Tight Channel
4. Bear Broad Channel
5. Bear Tight Channel
6. Breakout
""")

def _get_kline_with_ema_sync(klines, precision):
    """同步版本的 EMA 计算函数，用于在线程池中执行"""
    name = 'ema21'
    ema21 = talib.EMA(klines["close"], timeperiod=21)
    ema21 = ema21.round(precision)
    klines = klines.copy()
    klines[name] = ema21
    klines.dropna(subset=[name], inplace=True)
    return klines

def _generate_chart_image(df, window, title):
    """同步的绘图函数，用于在线程中执行"""
    fig, _ = plot_recent_klines(df, window, title)
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', bbox_inches='tight')
    plt.close(fig)  # 释放内存
    img_buffer.seek(0)
    return img_buffer.getvalue()

def _get_market_cycle_sync_worker(df, window, pid):
    """同步包装器，用于在独立线程中执行。涵盖了绘图和 AI 调用。"""
    image_bytes = _generate_chart_image(df, window, f'Recent {window} Bars')
    user_prompt = USER_PROMPT.format(chart_id=pid)
    # 在独立线程中使用 asyncio.run 运行异步的 request_ai
    return asyncio.run(request_ai(SYSTEM_PROMPT, user_prompt, [image_bytes], MarketCycle))

async def run_market_cycle_analysis(inst_id, precision, limit = 200):
    klines_target_cycle = await ok_client.get_klines(inst_id, 15, limit, exclude_unconfirmed_bar=False)
    klines_target_cycle = _get_kline_with_ema_sync(klines_target_cycle, precision)

    klines_high_cycle = await ok_client.get_klines(inst_id, 60, limit, exclude_unconfirmed_bar=False)
    klines_high_cycle = _get_kline_with_ema_sync(klines_high_cycle, precision)

    # 使用 asyncio.to_thread 将任务分发到多个线程，实现真正的多线程并发访问
    tasks = [
        asyncio.to_thread(_get_market_cycle_sync_worker, klines_target_cycle, 20, 2),
        asyncio.to_thread(_get_market_cycle_sync_worker, klines_target_cycle, 40, 4),
        asyncio.to_thread(_get_market_cycle_sync_worker, klines_target_cycle, 60, 6),
        asyncio.to_thread(_get_market_cycle_sync_worker, klines_target_cycle, 80, 8),

        asyncio.to_thread(_get_market_cycle_sync_worker, klines_high_cycle, 20, 12),
        asyncio.to_thread(_get_market_cycle_sync_worker, klines_high_cycle, 40, 14)
    ]
    
    # start_time = time.time()
    results = await asyncio.gather(*tasks)
    # end_time = time.time()
    
    # print(f"AI 并发任务总耗时: {end_time - start_time:.2f} 秒")
    data = {
        'inst_id': inst_id,
        'data': results
    }
    return data

if __name__ == '__main__':
    asyncio.run(run_market_cycle_analysis("BTC-USDT-SWAP", 2))


