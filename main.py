import asyncio
from ai.gemini_client import request_ai
from ai.models import TradingRangeResponse, TrendResponse
from ai.prompts import trend_prompts, trading_range_prompt
from visual.draw_klines import plot_candlestick
from visual.prepare_draw_data import get_kline_with_ema
from pathlib import Path
import matplotlib.pyplot as plt
import io

data = asyncio.run(get_kline_with_ema("BTC-USDT-SWAP", 15, 200, 2))

markers = [
    # {'timestamp': '2025-12-26 15:45:00', 'text': 'latest kline'},
]
fig, ax = plot_candlestick(data, title="BTC-USDT-SWAP 15-min Candlestick Chart", markers=markers)

# 保存到根目录下的 data 文件夹
# root_dir = Path(__file__).parent  # 获取项目根目录
# output_path = root_dir / "data" / "btc_kline_chart.png"
# plt.savefig(output_path, dpi=200, bbox_inches='tight')

img_buffer = io.BytesIO()
plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')
plt.close(fig)

# 获取图像字节数据
img_buffer.seek(0)  # 移动到缓冲区开头
image_bytes = img_buffer.getvalue()

async def run_ai():
    tr_task = request_ai(trading_range_prompt, image_bytes, TradingRangeResponse)
    tend_task = request_ai(trend_prompts, image_bytes, TrendResponse)

    tr_result, tend_result = await asyncio.gather(tr_task, tend_task)
    return tr_result, tend_result

tr_result, tend_result = asyncio.run(run_ai())

print(tr_result)
print("===================")
print(tend_result)