import asyncio
from ai.gemini_client import request_ai
from ai.models import TradingRangeResponse, TrendResponse, AutoTradeResponse
from ai.prompts import trend_prompts, trading_range_prompt
from ai.auto_prompts import auto_trade_prompts
from visual.draw_klines import plot_candlestick
from visual.prepare_draw_data import get_kline_with_ema
import matplotlib.pyplot as plt
import io
from common import tg_tools
import json
from coin_configs import coin_configs, evaluate_configs
from client import ok_client
from factory import ticket_factory
from datetime import datetime

async def run_inst(inst_id: str, interval: int, limit: int, precision: int):
    ticket_factory.cancel_algo_order(inst_id)

    klines = await get_kline_with_ema(inst_id, interval, limit, precision)
    
    # 取出klines df里面的最后10条数据，组装成dict，key从0-9，value每一个value都是ohlc的数据
    last_10_rows = klines.tail(10).reset_index(drop=True)
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
    
    # 将字典dump成str类型
    last_10_str = json.dumps(last_10_dict, ensure_ascii=False)

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

    auto_prompt = auto_trade_prompts.format(latest_klines=last_10_str)
    auto_result = await request_ai(auto_prompt, image_bytes, AutoTradeResponse)
    auto_response = json.dumps(auto_result, indent=2, ensure_ascii=False)
    print(auto_response)
    action = auto_result['action']
    if action != 'WAIT':
        if action == 'BUY':
            side = 'buy'
        else:
            side = 'sell'
        ticket_factory.order_algo_order(inst_id, side, 1,
                                                 auto_result['entry_price'],
                                                 auto_result['take_profit'],
                                                 auto_result['stop_loss'])
        end = str(datetime.now().replace(microsecond=0))
        eval_result = ticket_factory.evaluate_trade(inst_id, evaluate_configs['begin'], end)
        auto_response_to_tg = json.dumps({
            'symbol': inst_id,
            'ai_analysis': auto_result,
            'trading_history': eval_result
        }, indent=2, ensure_ascii=False)
        await tg_tools.tg_bot_http_post(auto_response_to_tg)


    # tr_prompt = trading_range_prompt.format(latest_klines=last_10_str)
    # trend_prompt = trend_prompts.format(latest_klines=last_10_str)
    # tr_task = request_ai(tr_prompt, image_bytes, TradingRangeResponse)
    # tend_task = request_ai(trend_prompt, image_bytes, TrendResponse)
    # tr_result, tend_result = await asyncio.gather(tr_task, tend_task)
    # tr_result['symbol'] = inst_id
    # tend_result['symbol'] = inst_id
    # tr_result['ai_focus_on'] = '震荡区间'
    # tend_result['ai_focus_on'] = '趋势行情'
    # tr_response = json.dumps(tr_result, indent=2, ensure_ascii=False)
    # tend_response = json.dumps(tend_result, indent=2, ensure_ascii=False)
    # 使用 json.dumps 格式化输出
    # print(tr_response)
    # print("===================")
    # print(tend_response)
    # if tr_result['direction'] != '等待':
    #     await tg_tools.tg_bot_http_post(tr_response)
    #
    # if tend_result['direction'] != '等待':
    #     await tg_tools.tg_bot_http_post(tend_response)

async def run_workflow():
    tickest = ticket_factory.get_ticket_data()
    if tickest:
        print(f'持仓中: {tickest}')
    else:
        tasks = []
        for coin_config in coin_configs:
            task = run_inst(coin_config['inst_id'], coin_config['interval'], coin_config['limit'], coin_config['precision'])
            tasks.append(task)

        await asyncio.gather(*tasks)

