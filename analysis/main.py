from ai.models import AutoTradeResponse
from client import ok_client
import asyncio
from visual import draw_klines
from ai.gemini_client import request_ai
import sys
import os
import io
from pathlib import Path
import matplotlib.pyplot as plt
from visual import prepare_draw_data
from ai.auto_prompts import auto_trade_prompts
import json


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


end_date = "2026-01-09 23:20:00"
klines_5min = asyncio.run(ok_client.get_klines_end_with_specify_time("BTC-USDT-SWAP", end_date, 5, 300, True))
klines_5min = prepare_draw_data.get_kline_with_ema_analysis(klines_5min, 2)

klines_1h = asyncio.run(ok_client.get_klines_end_with_specify_time("BTC-USDT-SWAP", end_date, 60, 300, False))
klines_1h = prepare_draw_data.get_kline_with_ema_analysis(klines_1h, 2)

image_bytes_5min = draw_plt_klines(klines_5min, '5min', f"5-min Candlestick Chart")
image_bytes_1h = draw_plt_klines(klines_1h, '1h', f"1-hour Candlestick Chart")

last_10_str_5min = get_last_10_rows(klines_5min)
last_10_str_1h = get_last_10_rows(klines_1h)

print("request ai")
auto_prompt = auto_trade_prompts.format(latest_klines_5min=last_10_str_5min, latest_klines_1h=last_10_str_1h)
auto_result = asyncio.run(request_ai(auto_prompt, [image_bytes_5min, image_bytes_1h], AutoTradeResponse))
auto_response = json.dumps(auto_result, indent=2, ensure_ascii=False)
print(auto_response)
