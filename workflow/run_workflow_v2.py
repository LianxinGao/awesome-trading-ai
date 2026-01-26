import asyncio
import matplotlib
matplotlib.use('Agg')  # 必须在导入 pyplot 之前设置后端，适用于无GUI环境
import matplotlib.pyplot as plt
from ai.gemini_client import request_ai
from filters import tech_filters
from ai.models import AutoTradeResponseV2
from ai.auto_prompts_v2 import auto_trade_system_prompts, auto_trade_user_prompts
from visual.draw_klines import plot_candlestick
import io
from common import tg_tools, comon_utils
import json
from coin_configs import target_coins, evaluate_configs
from client import ok_client
from factory import ticket_factory
from exp.get_market_cycle import UltimateMarketClassifier

classifier = UltimateMarketClassifier()

# 价格调整系数
long_target_coef = 0.998  # 做多止盈系数 (稍微调低，更容易成交)
short_target_coef = 1.002  # 做空止盈系数 (稍微调高，更容易成交)
long_stop_loss_coef = 0.995  # 做多止损系数 (稍微调低，增加容错)
short_stop_loss_coef = 1.005  # 做空止损系数 (稍微调高，增加容错)


def get_last_10_rows(df):
    # 优化：直接使用 iloc 获取最后10行并反转，避免多次创建中间 DataFrame
    n_rows = min(10, len(df))
    last_10_rows = df.iloc[-n_rows:].iloc[::-1].reset_index(drop=True)
    last_10_dict = {}
    for i in range(n_rows):
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
    try:
        # 使用 fig.savefig 而不是 plt.savefig，避免多线程环境下的全局状态问题
        fig.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight')
        # 获取图像字节数据
        img_buffer.seek(0)  # 移动到缓冲区开头
        image_bytes = img_buffer.getvalue()
    finally:
        # 确保资源被释放
        plt.close(fig)  # 关闭图表对象
        plt.close('all')  # 关闭所有matplotlib图表，防止内存泄漏
        img_buffer.close()  # 显式关闭缓冲区以释放内存
        # 清理matplotlib的缓存
        import gc
        gc.collect()  # 强制垃圾回收
    
    return image_bytes


async def find_trade_chance():
    tickets = ticket_factory.get_ticket_data()
    kline_tasks = []
    for coin in target_coins:
        task = _get_klines(coin['inst_id'], coin['intervals'], coin['limit'], coin['precision'], coin['sz'])
        kline_tasks.append(task)
    
    ai_tasks = []  # 在外部定义，确保 finally 块可以访问
    kline_results = None
    kline_results_dict = None
    
    # 使用 try-finally 确保资源释放
    try:
        kline_results = await asyncio.gather(*kline_tasks)
        kline_results_dict = {coin['inst_id']: coin for coin in kline_results}

        for coin in kline_results:
            task = asyncio.create_task(run_inst(coin['inst_id'], coin['klines_target_cycle'], coin['klines_high_cycle'],
                                                 coin['precision'], coin['sz']))
            ai_tasks.append(task)

        # 流式处理：每个任务完成就立即处理结果
        for coro in asyncio.as_completed(ai_tasks):
            result = None
            try:
                result = await coro
                action = result['action']
                inst_id = result['symbol']
                precision = result['precision']
                if action == 'WAIT':
                    print(f'{inst_id} 暂无交易机会')
                    continue
                coin_target_cycle = kline_results_dict[inst_id]['klines_target_cycle']
                pattern_filter = tech_filters.filter_by_patterns(coin_target_cycle, 5, action)
                count = pattern_filter.get('count', 0)
                has_conflict = pattern_filter.get('has_conflict', False)
                direction_match = pattern_filter.get('direction_match', False)
                if has_conflict or not direction_match or count == 0:
                    print(f'{inst_id} 被pattern_filter过滤')
                    continue

                entry_price = float(result['entry_price'])
                take_profit = float(result['take_profit'])
                stop_loss = float(result['stop_loss'])
                entry_type = result['entry_type']
                sz = result['sz']

                atr_filter = tech_filters.filter_by_atr_distance(coin_target_cycle, 20, entry_price, take_profit, 1)
                if not atr_filter.get('passed', False):
                    print(f'{inst_id} 被atr_filter过滤')
                    continue

                print(f'{inst_id} 符合交易条件')
                print(json.dumps(result, ensure_ascii=False, indent=4))
                ai_pos_side = 'long' if action == 'BUY' else 'short'
                ok_ticket = [ticket for ticket in tickets if ticket.inst_id == inst_id]
                if ok_ticket:
                    pos_side = ok_ticket[0].pos_side
                    if ai_pos_side != pos_side:
                        ticket_factory.close_position(inst_id)
                        if action == 'BUY':
                            side = 'buy'
                            take_profit = str(round(take_profit * long_target_coef, precision))
                            stop_loss = str(round(stop_loss * long_stop_loss_coef, precision))
                        else:
                            side = 'sell'
                            take_profit = str(round(take_profit * short_target_coef, precision))
                            stop_loss = str(round(stop_loss * short_stop_loss_coef, precision))
                        if entry_type == '市价委托':
                            ticket_factory.order_position(inst_id, side, sz, take_profit, stop_loss)
                        else:
                            ticket_factory.order_algo_order(inst_id, side, sz, str(entry_price), take_profit, stop_loss)
            except Exception as e:
                print(f"处理任务结果时发生错误: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # 确保清理结果数据
                if result is not None:
                    del result
    finally:
        # 确保所有任务都被清理
        for task in ai_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 释放 kline_results 内存
        import gc
        if kline_results is not None:
            del kline_results
        if kline_results_dict is not None:
            del kline_results_dict
        gc.collect()


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
    # 注意：get_single_mode 内部已经有 copy，这里不需要再 copy
    mode_tasks = [
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle, 20),
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle, 40),
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle, 60),
        asyncio.to_thread(classifier.get_single_mode, klines_target_cycle, 80),
        asyncio.to_thread(classifier.get_single_mode, klines_high_cycle, 20),
        asyncio.to_thread(classifier.get_single_mode, klines_high_cycle, 40),
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
    # 注意：_get_kline_with_ema_sync 内部已经有 copy，这里不需要再 copy
    klines_target_cycle_data, klines_high_cycle_data = await asyncio.gather(
        asyncio.to_thread(_get_kline_with_ema_sync, klines_target_cycle, precision),
        asyncio.to_thread(_get_kline_with_ema_sync, klines_high_cycle, precision)
    )

    # 3. 并发生成图表
    last_10_str_target_cycle = get_last_10_rows(klines_target_cycle_data)
    last_10_str_high_cycle = get_last_10_rows(klines_high_cycle_data)

    image_bytes_target_cycle, image_bytes_high_cycle = await asyncio.gather(
        asyncio.to_thread(draw_klines, klines_target_cycle_data, f"{inst_id}_15min_Candlestick_Chart"),
        asyncio.to_thread(draw_klines, klines_high_cycle_data, f"{inst_id}_1hour_Candlestick_Chart")
    )
    
    # 优化：使用完后显式释放 DataFrame 内存
    del klines_target_cycle_data, klines_high_cycle_data
    import gc
    gc.collect()  # 强制垃圾回收释放 DataFrame 内存

    auto_user_prompt = auto_trade_user_prompts.format(latest_klines_15min=last_10_str_target_cycle,
                                                      latest_klines_1h=last_10_str_high_cycle,
                                                      latest_15min_20_market_cycle=mode_target_20,
                                                      latest_15min_40_market_cycle=mode_target_40,
                                                      latest_15min_60_market_cycle=mode_target_60,
                                                      latest_15min_80_market_cycle=mode_target_80,
                                                      latest_1h_20_market_cycle=mode_high_20,
                                                      latest_1h_40_market_cycle=mode_high_40
                                                      )
    
    try:
        auto_result = await request_ai(auto_trade_system_prompts, auto_user_prompt,
                                       [image_bytes_target_cycle, image_bytes_high_cycle],
                                       AutoTradeResponseV2)
        
        # 检查 API 调用是否成功
        if auto_result is None:
            print(f"{inst_id} AI API 调用失败，返回默认响应")
            # 返回一个默认的 WAIT 响应，避免程序崩溃
            auto_result_dict = {
                'action': 'WAIT',
                'entry_price': '0',
                'take_profit': '0',
                'stop_loss': '0',
                'entry_type': '市价委托',
                'summary': 'AI API 调用失败',
                'symbol': inst_id,
                'sz': sz,
                'precision': precision
            }
        else:
            auto_result_dict = dict(auto_result)
            auto_result_dict['symbol'] = inst_id
            auto_result_dict['sz'] = sz
            auto_result_dict['precision'] = precision
    except Exception as e:
        print(f"{inst_id} AI 调用发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        # 返回默认响应，确保程序继续运行
        auto_result_dict = {
            'action': 'WAIT',
            'entry_price': '0',
            'take_profit': '0',
            'stop_loss': '0',
            'entry_type': '市价委托',
            'summary': f'AI 调用异常: {str(e)}',
            'symbol': inst_id,
            'sz': sz,
            'precision': precision
        }
    finally:
        # 释放图像字节数据内存
        del image_bytes_target_cycle, image_bytes_high_cycle
        gc.collect()
    
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
    try:
        for coin_config in target_coins:
            inst_id = coin_config['inst_id']
            # leverage = coin_config['leverage']
            # ok_client.set_leverage(inst_id, leverage, TdMode.CROSS)
            # print(f"设置{inst_id}的合约杠杆为{leverage}倍")
            ticket_factory.cancel_order(inst_id)

        await find_trade_chance()
    finally:
        # 每次工作流执行完后强制垃圾回收，防止内存累积
        import gc
        gc.collect()


if __name__ == '__main__':
    import asyncio

    asyncio.run(run_workflow())
