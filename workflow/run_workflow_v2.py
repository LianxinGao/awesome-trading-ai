import asyncio
from ai.gemini_client import request_ai
from filters import tech_filters
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
from coin_configs import target_coins, evaluate_configs
from client import ok_client
from factory import ticket_factory
from datetime import datetime, timedelta
from exp.get_market_cycle import UltimateMarketClassifier

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


def _get_kline_with_ema_sync(klines, precision):
    """同步版本的 EMA 计算函数，用于在线程池中执行"""
    import talib
    name = 'ema21'
    ema21 = talib.EMA(klines["close"], timeperiod=21)
    ema21 = ema21.round(precision)
    klines = klines.copy()
    klines[name] = ema21
    klines.dropna(subset=[name], inplace=True)
    return klines


def draw_klines(klines_data, title, markers=None, entry_price=None, entry_type=None):
    if not markers:
        markers = []
    fig, ax = plot_candlestick(klines_data, title=title, markers=markers, entry_price=entry_price,
                               entry_type=entry_type)

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')

    plt.close(fig)

    # 获取图像字节数据
    img_buffer.seek(0)  # 移动到缓冲区开头
    image_bytes = img_buffer.getvalue()
    return image_bytes


async def find_trade_chance():
    tickets = ticket_factory.get_ticket_data()
    kline_tasks = []
    for coin in target_coins:
        task = _get_klines(coin['inst_id'], coin['intervals'], coin['limit'], coin['precision'], coin['sz'])
        kline_tasks.append(task)
    kline_results = await asyncio.gather(*kline_tasks)
    kline_results_dict = {coin['inst_id']: coin for coin in kline_results}

    ai_tasks = []
    for coin in kline_results:
        task = run_inst(coin['inst_id'], coin['klines_target_cycle'], coin['klines_high_cycle'],
                        coin['precision'], coin['sz'])
        ai_tasks.append(task)
    ai_results = await asyncio.gather(*ai_tasks)

    for result in ai_results:
        if result['action'] == 'WAIT':
            continue

        action = result['action']
        inst_id = result['symbol']
        coin_target_cycle = kline_results_dict[inst_id]['klines_target_cycle']
        pattern_filter = tech_filters.filter_by_patterns(coin_target_cycle, 5, action)
        count = pattern_filter.get('count', 0)
        has_conflict = pattern_filter.get('has_conflict', False)
        direction_match = pattern_filter.get('direction_match', False)
        if has_conflict or not direction_match or count == 0:
            continue

        entry_price = result['entry_price']
        take_profit = result['take_profit']
        stop_loss = result['stop_loss']
        entry_type = result['entry_type']
        sz = result['sz']

        atr_filter = tech_filters.filter_by_atr_distance(coin_target_cycle, 20, entry_price, take_profit, 1)
        if not atr_filter.get('passed', False):
            continue


        ai_pos_side = 'long' if action == 'BUY' else 'short'
        ok_ticket = [ticket for ticket in tickets if ticket.inst_id == inst_id]
        if ok_ticket:
            pos_side = ok_ticket[0].pos_side
            if ai_pos_side != pos_side:
                ticket_factory.close_position(inst_id)
                if action == 'BUY':
                    side = 'buy'
                else:
                    side = 'sell'
                if entry_type == '市价委托':
                    ticket_factory.order_position(inst_id, side, sz, take_profit, stop_loss)
                else:
                    ticket_factory.order_algo_order(inst_id, side, sz, entry_price, take_profit, stop_loss)


async def _get_klines(inst_id: str, intervals: list[int], limit: int, precision: int, sz: float):
    klines_target_cycle = await ok_client.get_klines(inst_id, intervals[0], limit, exclude_unconfirmed_bar=True)
    klines_high_cycle = await ok_client.get_klines(inst_id, intervals[1], limit, exclude_unconfirmed_bar=False)
    data_dict = {
        'inst_id': inst_id,
        'klines_target_cycle': klines_target_cycle,
        'klines_high_cycle': klines_high_cycle,
        'precision': precision,
        'sz': sz
    }
    return data_dict


async def run_inst(inst_id, klines_target_cycle, klines_high_cycle, precision: int, sz: float):
    # 并发执行所有同步阻塞操作
    # 1. 并发计算所有市场周期模式
    mode_tasks = [
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle.copy(), 20),
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle.copy(), 40),
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle.copy(), 60),
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle.copy(), 80),
        asyncio.to_thread(classifier.get_single_mode, klines_high_cycle.copy(), 20),
        asyncio.to_thread(classifier.get_single_mode, klines_high_cycle.copy(), 40),
    ]
    modes = await asyncio.gather(*mode_tasks)
    mode_target_20, mode_target_40, mode_target_60, mode_target_80, mode_high_20, mode_high_40 = modes
    
    print(f'{inst_id} target 20周期: {mode_target_20}')
    print(f'{inst_id} target 40周期: {mode_target_40}')
    print(f'{inst_id} target 60周期: {mode_target_60}')
    print(f'{inst_id} target 80周期: {mode_target_80}')
    print(f'{inst_id} high 20周期: {mode_high_20}')
    print(f'{inst_id} high 40周期: {mode_high_40}')

    # 2. 并发计算 EMA 数据
    klines_target_cycle_data, klines_high_cycle_data = await asyncio.gather(
        asyncio.to_thread(_get_kline_with_ema_sync, klines_target_cycle.copy(), precision),
        asyncio.to_thread(_get_kline_with_ema_sync, klines_high_cycle.copy(), precision)
    )

    # 3. 并发生成图表
    last_10_str_target_cycle = get_last_10_rows(klines_target_cycle_data)
    last_10_str_high_cycle = get_last_10_rows(klines_high_cycle_data)

    image_bytes_target_cycle, image_bytes_high_cycle = await asyncio.gather(
        asyncio.to_thread(draw_klines, klines_target_cycle_data, f"{inst_id}_15min_Candlestick_Chart"),
        asyncio.to_thread(draw_klines, klines_high_cycle_data, f"{inst_id}_1hour_Candlestick_Chart")
    )

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
    auto_result_dict = dict(auto_result)
    auto_result_dict['symbol'] = inst_id
    auto_result_dict['sz'] = sz
    # auto_response = json.dumps(auto_result_dict, indent=2, ensure_ascii=False)
    return auto_result_dict
    # print(auto_response)
    # action = auto_result['action']
    # if action != 'WAIT':
    #     entry_type = auto_result['entry_type']
    #     save_info = SaveOrderInfo(
    #         time=next_kline_time_str,
    #         action=auto_result['action'],
    #         reason=auto_result['summary'],
    #         entry_price=auto_result['entry_price'],
    #         take_profit_price=auto_result['take_profit'],
    #         stop_loss_price=auto_result['stop_loss']
    #     )
    #     comon_utils.save_ticket(inst_id, save_info.model_dump_json(indent=4))
    #
    #     if action == 'BUY':
    #         side = 'buy'
    #     else:
    #         side = 'sell'
    #     if entry_type == '市价委托':
    #         ticket_factory.order_position(inst_id, side, sz, auto_result['take_profit'], auto_result['stop_loss'])
    #     else:
    #         ticket_factory.order_algo_order(inst_id, side, sz,
    #                                         auto_result['entry_price'],
    #                                         auto_result['take_profit'],
    #                                         auto_result['stop_loss'])
    #     end = str(datetime.now().replace(microsecond=0))
    #     eval_result = ticket_factory.evaluate_trade(inst_id, evaluate_configs['begin'], end)
    #     auto_response_to_tg = json.dumps({
    #         'symbol': inst_id,
    #         'ai_analysis': auto_result,
    #         'trading_history': eval_result
    #     }, indent=2, ensure_ascii=False)
    # await tg_tools.tg_bot_http_post(auto_response_to_tg)


async def run_workflow():
    for coin_config in target_coins:
        inst_id = coin_config['inst_id']
        leverage = coin_config['leverage']
        ok_client.set_leverage(inst_id, leverage, TdMode.CROSS)
        print(f"设置{inst_id}的合约杠杆为{leverage}倍")
        ticket_factory.cancel_order(inst_id)

    await find_trade_chance()


if __name__ == '__main__':
    import asyncio

    asyncio.run(run_workflow())
