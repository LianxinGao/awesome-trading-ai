from client import ok_client
import asyncio
from visual import draw_klines
from ai.gemini_client import request_ai, request_ai_direct
import sys
import os
import io
from pathlib import Path
import matplotlib.pyplot as plt
from visual import prepare_draw_data
from analysis.analysis_prompts import analysis_trade_prompts
import json
from pydantic import BaseModel, Field
from typing import Literal
from exp.get_market_cycle import UltimateMarketClassifier


class AnalysisTradeResponse(BaseModel):
    market_cycle_analysis: str = Field(description="市场当前所处周期")
    patterns_identified: str = Field(description="模式识别")
    summary: str = Field(description="理由总结")
    sr: str = Field(description="支撑位和阻力位分析")
    action: Literal['BUY', 'SELL', 'WAIT'] = Field(description="多空方向")
    entry_type: str = Field(description="计划委托/市价委托")
    entry_price: str = Field(default="", description="入场价")
    stop_loss: str = Field(default="", description="止损价")
    take_profit: str = Field(default="", description="止盈价")
    early_close_strategy: str = Field(default="", description="提前平仓策略")

def get_last_10_rows(df):
    last_10_rows = df.tail(10).reset_index(drop=True)
    last_10_dict = {}
    for i in range(min(10, len(last_10_rows))):
        row = last_10_rows.iloc[i]
        last_10_dict[i] = {
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'ema21': row['ema21']
        }
    last_10_str = json.dumps(last_10_dict, ensure_ascii=False)
    return last_10_str


def draw_plt_klines(klines_data, tail_name, title, markers=None, entry_price=None, entry_type=None):
    if not markers:
        markers = []
    fig, ax = draw_klines.plot_candlestick(klines_data, title=title, markers=markers, entry_price=entry_price,
                                           entry_type=entry_type)
    img_buffer = io.BytesIO()
    # 保存到根目录下的 data 文件夹
    root_dir = Path(__file__).parent.parent  # 获取项目根目录
    output_path = root_dir / "data" / f"kline_chart_review_{tail_name}.png"
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)

    # 获取图像字节数据
    img_buffer.seek(0)  # 移动到缓冲区开头
    image_bytes = img_buffer.getvalue()
    return image_bytes


classifier = UltimateMarketClassifier()

end_date = "2026-01-12 20:45:01"
klines_5min = asyncio.run(ok_client.get_klines_end_with_specify_time("BTC-USDT-SWAP", end_date, 5, 300, True))

state20 = classifier.get_single_mode(klines_5min, window=20, z_threshold=1.5)
state40 = classifier.get_single_mode(klines_5min, window=40, z_threshold=1.5)
state60 = classifier.get_single_mode(klines_5min, window=60, z_threshold=1.5)
state80 = classifier.get_single_mode(klines_5min, window=80, z_threshold=1.5)
print(state20)
print(state40)
print(state60)
print(state80)

klines_5min = prepare_draw_data.get_kline_with_ema_analysis(klines_5min, 2)

klines_1h = asyncio.run(ok_client.get_klines_end_with_specify_time("BTC-USDT-SWAP", end_date, 60, 300, False))
klines_1h = prepare_draw_data.get_kline_with_ema_analysis(klines_1h, 2)

image_bytes_5min = draw_plt_klines(klines_5min, '5min', f"5-min Candlestick Chart")
image_bytes_1h = draw_plt_klines(klines_1h, '1h', f"1-hour Candlestick Chart")

last_10_str_5min = get_last_10_rows(klines_5min)
# last_10_str_1h = get_last_10_rows(klines_1h)

print("request ai")
auto_prompt = analysis_trade_prompts.format(latest_klines_5min=last_10_str_5min,
                                            latest_20_market_cycle=state20,
                                            latest_40_market_cycle=state40,
                                            latest_60_market_cycle=state60,
                                            latest_80_market_cycle=state80,
                                            )
auto_result = asyncio.run(request_ai_direct(auto_prompt, [image_bytes_5min, image_bytes_1h]))
print(auto_result)
# auto_response = json.dumps(auto_result, indent=2, ensure_ascii=False)
# print(auto_response)
