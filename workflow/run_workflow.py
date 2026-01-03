import asyncio
from ai.gemini_client import request_ai
from ai.models import AutoTradeResponse, MonitoringResponse
from ai.auto_prompts import auto_trade_prompts, monitoring_prompts
from client.ok_models import TdMode
from visual.draw_klines import plot_candlestick
from visual.prepare_draw_data import get_kline_with_ema
import matplotlib.pyplot as plt
import io
from common import tg_tools
import json
from coin_configs import coin_configs, evaluate_configs, monitoring_configs
from client import ok_client
from factory import ticket_factory
from datetime import datetime

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

def draw_klines(klines_data, title, markers = None, entry_price = None, entry_type = None):
    if not markers:
        markers = []
    fig, ax = plot_candlestick(klines_data, title=title, markers=markers, entry_price=entry_price, entry_type=entry_type)
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)

    # 获取图像字节数据
    img_buffer.seek(0)  # 移动到缓冲区开头
    image_bytes = img_buffer.getvalue()
    return image_bytes

async def run_inst(inst_id: str, intervals: list[int], limit: int, precision: int, sz: int):
    ticket_factory.cancel_algo_order(inst_id)

    klines_15min = await get_kline_with_ema(inst_id, intervals[0], limit, precision)
    klines_4h = await get_kline_with_ema(inst_id, intervals[1], limit, precision, False)
    
    last_10_str_15min = get_last_10_rows(klines_15min)
    last_10_str_4h = get_last_10_rows(klines_4h)

    # markers = [
    #     # {'timestamp': '2025-12-26 15:45:00', 'text': 'latest kline'},
    # ]
    image_bytes_15min = draw_klines(klines_15min, f"{inst_id} 15-min Candlestick Chart")
    image_bytes_4h = draw_klines(klines_4h, f"{inst_id} 4h Candlestick Chart")


    auto_prompt = auto_trade_prompts.format(latest_klines_15min=last_10_str_15min,
                                            latest_klines_4h=last_10_str_4h)
    auto_result = await request_ai(auto_prompt, [image_bytes_15min, image_bytes_4h], AutoTradeResponse)
    auto_response = json.dumps(auto_result, indent=2, ensure_ascii=False)
    print(auto_response)
    action = auto_result['action']
    if action != 'WAIT':
        if action == 'BUY':
            side = 'buy'
        else:
            side = 'sell'
        ticket_factory.order_algo_order(inst_id, side, sz,
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


async def run_monitoring(inst_id, interval, limit: int, precision: int, entry_price, entry_type):
    klines_15min = await get_kline_with_ema(inst_id, interval, limit, precision)
    image_bytes_15min = draw_klines(klines_15min, f"{inst_id} 15-min Candlestick Chart",
                                    entry_price=entry_price, entry_type=entry_type)
    monitor_result = await request_ai(monitoring_prompts, [image_bytes_15min], MonitoringResponse)
    monitor_response = json.dumps(monitor_result, indent=2, ensure_ascii=False)
    print(monitor_response)

    action = monitor_result['action']
    if action == 'EXIT':
        ticket_factory.close_position(inst_id)
        await tg_tools.tg_bot_http_post(monitor_response)



async def run_workflow():
    tickest = ticket_factory.get_ticket_data()
    if tickest:
        print(f'持仓中: {tickest}')
        # ticket = tickest[0]
        # for config in monitoring_configs:
        #     inst_id = config['inst_id']
        #     interval = config['interval']
        #     limit = config['limit']
        #     precision = config['precision']
        #     entry_price = float(ticket.avg_px)
        #     entry_type = 'buy' if ticket.pos_side == 'long' else 'sell'
        #     await run_monitoring(inst_id, interval, limit, precision, entry_price, entry_type)

    else:
        tasks = []
        for coin_config in coin_configs:
            inst_id = coin_config['inst_id']
            intervals = coin_config['intervals']
            limit = coin_config['limit']
            precision = coin_config['precision']
            sz = coin_config['sz']
            leverage = coin_config['leverage']

            ok_client.set_leverage(inst_id, leverage, TdMode.CROSS)
            print(f"设置{inst_id}的合约杠杆为{leverage}倍")

            task = run_inst(inst_id, intervals, limit, precision, sz)
            tasks.append(task)

        await asyncio.gather(*tasks)

