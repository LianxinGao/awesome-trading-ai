import asyncio
from ai.gemini_client import request_ai
from ai.models import AutoTradeResponse, MonitoringResponse, SaveOrderInfo, AutoTradeResponseV2
from ai.auto_prompts_v2 import auto_trade_system_prompts, auto_trade_user_prompts, monitoring_user_prompts, \
    monitoring_system_prompts
from client.ok_models import TdMode
from visual.draw_klines import plot_candlestick
from visual.prepare_draw_data import get_kline_with_ema
import matplotlib.pyplot as plt
import io
from common import tg_tools, comon_utils
import json
from coin_configs import coin_configs, evaluate_configs, monitoring_configs
from client import ok_client
from factory import ticket_factory
from datetime import datetime, timedelta
from exp.get_market_cycle import UltimateMarketClassifier
from pathlib import Path

classifier = UltimateMarketClassifier()


def get_last_10_rows(df):
    last_10_rows = df.tail(10).reset_index(drop=True)
    last_10_rows = last_10_rows[::-1].reset_index(drop=True)
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


def draw_klines(klines_data, title, markers=None, entry_price=None, entry_type=None):
    if not markers:
        markers = []
    fig, ax = plot_candlestick(klines_data, title=title, markers=markers, entry_price=entry_price,
                               entry_type=entry_type)

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')

    root_dir = Path(__file__).parent.parent  # 获取项目根目录
    output_path = root_dir / "data" / f"kline_chart_pro_{title}.png"
    plt.savefig(output_path, dpi=200, bbox_inches='tight')

    plt.close(fig)

    # 获取图像字节数据
    img_buffer.seek(0)  # 移动到缓冲区开头
    image_bytes = img_buffer.getvalue()
    return image_bytes


async def run_inst_v2(inst_id: str, intervals: list[int], limit: int, precision: int, sz: int):
    ticket_factory.cancel_algo_order(inst_id)

    klines_target_cycle = await ok_client.get_klines(inst_id, intervals[0], limit, exclude_unconfirmed_bar=True)
    klines_high_cycle = await ok_client.get_klines(inst_id, intervals[1], limit, exclude_unconfirmed_bar=False)

    mode_target_20 = classifier.get_single_mode(klines_target_cycle.copy(), window=20)
    mode_target_40 = classifier.get_single_mode(klines_target_cycle.copy(), window=40)
    mode_target_60 = classifier.get_single_mode(klines_target_cycle.copy(), window=60)
    mode_target_80 = classifier.get_single_mode(klines_target_cycle.copy(), window=80)
    print(f'target 20周期: {mode_target_20}')
    print(f'target 40周期: {mode_target_40}')
    print(f'target 60周期: {mode_target_60}')
    print(f'target 80周期: {mode_target_80}')
    mode_high_20 = classifier.get_single_mode(klines_high_cycle.copy(), window=20)
    mode_high_40 = classifier.get_single_mode(klines_high_cycle.copy(), window=40)
    print(f'high 20周期: {mode_high_20}')
    print(f'high 40周期: {mode_high_40}')

    klines_target_cycle_data = await get_kline_with_ema(klines_target_cycle.copy(), precision)
    klines_high_cycle_data = await get_kline_with_ema(klines_high_cycle.copy(), precision)

    last_kline_time = klines_target_cycle_data['timestamp'].iloc[-1]
    last_kline_datetime = datetime.strptime(last_kline_time, '%Y-%m-%d %H:%M:%S')
    next_kline_time = last_kline_datetime + timedelta(minutes=5)
    next_kline_time_str = next_kline_time.strftime("%Y-%m-%d %H:%M:%S")

    last_10_str_target_cycle = get_last_10_rows(klines_target_cycle_data)
    last_10_str_high_cycle = get_last_10_rows(klines_high_cycle_data)

    # print(last_10_str_target_cycle)
    # print("=================")
    # print(last_10_str_high_cycle)

    # markers = [
    #     # {'timestamp': '2025-12-26 15:45:00', 'text': 'latest kline'},
    # ]
    image_bytes_target_cycle = draw_klines(klines_target_cycle_data, f"15min_Candlestick_Chart")
    image_bytes_high_cycle = draw_klines(klines_high_cycle_data, f"1hour_Candlestick_Chart")

    auto_user_prompt = auto_trade_user_prompts.format(latest_klines_15min=last_10_str_target_cycle,
                                                      latest_klines_1h=last_10_str_high_cycle,
                                                      latest_15min_20_market_cycle=mode_target_20,
                                                      latest_15min_40_market_cycle=mode_target_40,
                                                      latest_15min_60_market_cycle=mode_target_60,
                                                      latest_15min_80_market_cycle=mode_target_80,
                                                      latest_1h_20_market_cycle=mode_high_20,
                                                      latest_1h_40_market_cycle=mode_high_40
                                                      )
    auto_result = await request_ai(auto_trade_system_prompts, auto_user_prompt,
                                   [image_bytes_target_cycle, image_bytes_high_cycle],
                                   AutoTradeResponseV2)
    auto_response = json.dumps(auto_result, indent=2, ensure_ascii=False)
    print(auto_response)
    action = auto_result['action']
    if action != 'WAIT':
        entry_type = auto_result['entry_type']
        save_info = SaveOrderInfo(
            time=next_kline_time_str,
            action=auto_result['action'],
            reason=auto_result['summary'],
            entry_price=auto_result['entry_price'],
            take_profit_price=auto_result['take_profit'],
            stop_loss_price=auto_result['stop_loss']
        )
        comon_utils.save_ticket(inst_id, save_info.model_dump_json(indent=4))

        if action == 'BUY':
            side = 'buy'
        else:
            side = 'sell'
        if entry_type == '市价委托':
            ticket_factory.order_position(inst_id, side, sz, auto_result['take_profit'], auto_result['stop_loss'])
        else:
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
        # await tg_tools.tg_bot_http_post(auto_response_to_tg)


async def run_monitoring(inst_id, interval, limit: int, precision: int, entry_price, entry_type,
                         time, tp, sl, reason):
    klines_15min = await ok_client.get_klines(inst_id, interval, limit, exclude_unconfirmed_bar=True)

    markers = [
        {'timestamp': time, 'text': 'Entry Bar'},
    ]
    prompt = monitoring_user_prompts.format(sl=sl, tp=tp, reason=reason)
    image_bytes_15min = draw_klines(klines_15min, f"monitoring_15min_Candlestick_Chart", markers=markers,
                                   entry_price=entry_price,
                                   entry_type=entry_type)
    monitor_result = await request_ai(monitoring_system_prompts, prompt, [image_bytes_15min], MonitoringResponse)
    monitor_response = json.dumps(monitor_result, indent=2, ensure_ascii=False)
    print(monitor_response)

    action = monitor_result['action']
    if action == 'EXIT':
        ticket_factory.close_position(inst_id)
        # await tg_tools.tg_bot_http_post(monitor_response)


async def run_workflow():
    tickest = ticket_factory.get_ticket_data()
    if tickest:
        print(f'持仓中: {tickest}')
        # for config in monitoring_configs:
        #     inst_id = config['inst_id']
        #     ok_ticket = [ticket for ticket in tickest if ticket.inst_id == inst_id]
        #     ticket = comon_utils.load_latest_ticket(inst_id, SaveOrderInfo)
        #     # comon_utils.save_confirmed_ticket(inst_id, ticket.model_dump_json(indent=4))
        #     interval = config['interval']
        #     limit = config['limit']
        #     precision = config['precision']
        #     entry_price = float(ticket.entry_price) if ticket.entry_price else float(ok_ticket[0].avg_px)
        #     entry_type = ticket.action
        #     # early_close_strategy = ticket.early_close_strategy
        #     tp = ticket.take_profit_price
        #     sl = ticket.stop_loss_price
        #     reason = ticket.reason
        #     time = ticket.time
        #     await run_monitoring(inst_id, interval, limit, precision, entry_price, entry_type,
        #                          time, tp, sl, reason)

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

            task = run_inst_v2(inst_id, intervals, limit, precision, sz)
            tasks.append(task)

        await asyncio.gather(*tasks)


if __name__ == '__main__':
    import asyncio

    asyncio.run(run_workflow())
