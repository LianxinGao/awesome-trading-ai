import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx
import okx.Account as Account
import okx.Trade as Trade
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import okx.TradingData as TradingData

from client.ok_models import CompletedTicket
from client.ok_models import OrderType, TdMode, Ticket
import os
from common.comon_utils import move_time_backward
from datetime import datetime, timedelta
import pandas as pd
from common.comon_utils import get_date
from dotenv import load_dotenv

from common import comon_utils

load_dotenv()

API_KEY = os.environ["OK_API_KEY"]
SECRET_KEY = os.environ["OK_SECRET_KEY"]
PASSPHRASE = os.environ["OK_PASSPHRASE"]
flag = "0"  # 实盘:0 , 模拟盘:1
accountAPI = Account.AccountAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
tradeAPI = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
marketAPI = MarketData.MarketAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
publicAPI = PublicData.PublicAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
tradingDataAPI = TradingData.TradingDataAPI(flag)


def _get_timestamp() -> str:
    """生成时间戳"""
    now = time.time()
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(now))
    milliseconds = f"{int(now * 1000) % 1000:03d}"
    return f"{timestamp}.{milliseconds}Z"


def _create_headers(method: str, endpoint: str, params: dict, body_str: str = None) -> dict:
    timestamp = _get_timestamp()
    method = method.upper()
    if method == 'GET':
        query_string = urlencode(params) if params else ''
        full_path = f"{endpoint}?{query_string}" if query_string else endpoint
        message = f"{timestamp}{method}{full_path}"
    else:
        # POST 等需要把原始请求体拼接到签名中
        message = f"{timestamp}{method}{endpoint}{body_str or ''}"
    signature = base64.b64encode(hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).digest()).decode()
    return {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
        'OK-ACCESS-SIGN': signature,
        'Content-Type': 'application/json'
    }


def get_bar_size(interval_minutes: int):
    if interval_minutes == 15:
        return "15m"
    elif interval_minutes == 5:
        return "5m"
    elif interval_minutes == 30:
        return "30m"
    elif interval_minutes == 60:
        return "1H"
    elif interval_minutes == 120:
        return "2H"
    elif interval_minutes == 240:
        return "4H"
    elif interval_minutes == 1440:
        return "1D"
    elif interval_minutes == 2880:
        return "2D"
    elif interval_minutes == 10080:
        return "1W"
    else:
        raise Exception("Invalid interval_minutes value")


def place_order(order_type: OrderType, inst_id, side: str, sz: str,
                tp_trigger_px, sl_trigger_px, td_mode: TdMode, px="",
                ):
    if order_type == OrderType.LIMIT:
        result = tradeAPI.place_order(
            instId=inst_id, tdMode=td_mode.value,
            side=side, ordType=order_type.value,
            sz=sz, px=px,
            attachAlgoOrds=[
                {
                    "tpTriggerPx": tp_trigger_px,
                    "tpOrdPx": "-1",
                },
                {
                    "slTriggerPx": sl_trigger_px,
                    "slOrdPx": "-1",
                }
            ]
        )
    elif order_type == OrderType.OPTIMAL_LIMIT_LOC:
        result = tradeAPI.place_order(
            instId=inst_id, tdMode=td_mode.value, side=side,
            ordType=order_type.value, sz=sz,
            attachAlgoOrds=[
                {
                    "tpTriggerPx": tp_trigger_px,
                    "tpOrdPx": "-1",
                },
                {
                    "slTriggerPx": sl_trigger_px,
                    "slOrdPx": "-1",
                }
            ]
        )
    else:
        raise Exception("Invalid order_type")
    return result


# 计划委托
def place_algo_order(inst_id, side, sz, trigger_px, tp_trigger_px, sl_trigger_px):
    result = tradeAPI.place_algo_order(
        instId=inst_id,
        tdMode='cross',
        side=side,
        ordType='trigger',
        sz=sz,
        triggerPx=trigger_px,
        orderPx="-1",
        attachAlgoOrds=[
            {
                "tpTriggerPx": tp_trigger_px,
                "tpOrdPx": "-1",
            },
            {
                "slTriggerPx": sl_trigger_px,
                "slOrdPx": "-1",
            }
        ]
    )
    return result


def modify_algo_order(inst_id: str, algo_id: str, tp_trigger_px, sl_trigger_px):
    result = tradeAPI.amend_algo_order(
        instId=inst_id,
        algoId=algo_id,
        newSlTriggerPx=tp_trigger_px,
        newTpOrdPx="-1",
        newTpTriggerPx=sl_trigger_px,
        newSlOrdPx="-1"
    )
    print(result)


def get_pending_algo_order_id():
    results = tradeAPI.order_algos_list(
        ordType="trigger"
    )
    # algo_id = results['data'][0]['algoId']
    data = results['data']
    if data:
        algo_id = data[0]['algoId']
    else:
        algo_id = ""
    return algo_id


def cancel_algo_order(inst_id, algo_id):
    algo_orders = [{"instId": inst_id, "algoId": algo_id}]
    result = tradeAPI.cancel_algo_order(algo_orders)
    return result


def cancel_order(inst_id: str, order_id: str):
    result = tradeAPI.cancel_order(instId=inst_id, ordId=order_id)
    if result and result["code"] == "0":
        return True
    else:
        return False


def get_pending_order(inst_id: str):
    result = tradeAPI.get_order_list(instId=inst_id)
    if result and result["code"] == "0":
        if result['data']:
            return result['data'][0]['ordId']
        else:
            return ""
    else:
        return ""


def close_position(inst_id, mgn_mode: TdMode):
    result = tradeAPI.close_positions(
        instId=inst_id,
        mgnMode=mgn_mode.value,
        autoCxl="true"
    )
    if result and result["code"] == "0":
        return True
    else:
        return False


def get_all_position_history(begin: str, end: str):
    """
    Args:
        begin: "1754409600000"
        end: "1754470800000"
    """
    tickets = []
    results = accountAPI.get_positions_history(
        before=begin,
        after=end
    )['data']
    for result in results:
        tickets.append(CompletedTicket(
            inst_id=result["instId"],
            direction=result['direction'],
            open_avg_px=result["openAvgPx"],
            close_avg_px=result["closeAvgPx"],
            pnl=result["pnl"],
            fee=result["fee"],
            realized_pnl=result["realizedPnl"],
            completed_time=get_date(int(result["uTime"]))
        ))
    return tickets

def get_position_history(inst_id: str, begin: str, end: str):
    """
    Args:
        begin: "1754409600000"
        end: "1754470800000"
    """
    tickets = []
    results = accountAPI.get_positions_history(
        instId=inst_id,
        before=begin,
        after=end
    )['data']
    for result in results:
        tickets.append(CompletedTicket(
            inst_id=result["instId"],
            direction=result['direction'],
            open_avg_px=result["openAvgPx"],
            close_avg_px=result["closeAvgPx"],
            pnl=result["pnl"],
            fee=result["fee"],
            realized_pnl=result["realizedPnl"],
            completed_time=get_date(int(result["uTime"]))
        ))
    return tickets


def set_leverage(inst_id: str, lever: str, mgn_mode: TdMode):
    result = accountAPI.set_leverage(
        instId=inst_id,
        lever=lever,
        mgnMode=mgn_mode.value
    )

    if result and result.get("code") == "0":
        return True
    else:
        return False


def get_now():
    date_string = publicAPI.get_system_time()['data'][0]['ts']
    timestamp_ms = int(date_string)
    date_object = datetime.fromtimestamp(timestamp_ms / 1000)
    formatted_date = date_object.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_date


async def get_klines_end_with_specify_time(inst_id: str, end_date: str, interval_minutes=60, n=200, exclude_unconfirmed_bar=False) -> pd.DataFrame:
    """
    获取指定结束时间之前的n个K线数据（回撤获取）
    
    Args:
        inst_id: 交易对ID
        end_date: 结束日期，格式为 'YYYY-MM-DD HH:MM:SS'
        interval_minutes: K线周期（分钟）
        n: 需要获取的K线数量
        exclude_unconfirmed_bar: 是否排除未确认的K线
    
    Returns:
        DataFrame: 包含K线数据的DataFrame
    """
    end_timestamp = comon_utils.get_timestamp(end_date)

    all_klines = []
    current_after = end_timestamp  # 用于分页的时间戳，初始为结束时间

    while True:
        # 如果exclude_unconfirmed_bar=True，可能需要获取更多数据以确保有足够的确认K线
        batch_size = 200
        res = marketAPI.get_candlesticks(
            instId=inst_id,
            after=current_after,  # after参数：获取此时间戳之前（更旧）的数据
            bar=get_bar_size(interval_minutes),
            limit=batch_size
        )['data']

        if not res:
            break

        # 在处理数据之前，先保存最后一条数据的原始时间戳（用于分页）
        # API返回的数据是按时间倒序的（最新的在前），最后一条是最早的
        last_timestamp = int(res[-1][0])

        # 处理当前批次的数据
        batch_klines = []
        for line in res:
            line[0] = str(datetime.fromtimestamp(int(line[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S'))
            batch_klines.append([line[0], line[1], line[2], line[3], line[4], line[5], line[8]])

        # 添加到总数据中
        all_klines.extend(batch_klines)

        # 更新分页参数：将after设置为最后一条数据的时间戳，以便下次获取更早的数据
        current_after = last_timestamp

        # 检查是否已经获取到足够的数据（需要先处理数据再检查）
        df_temp = pd.DataFrame(all_klines,
                               columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'confirm'])
        df_temp = df_temp.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
        
        # 如果需要排除未确认的K线，检查确认的K线数量
        if exclude_unconfirmed_bar:
            df_confirmed = df_temp[df_temp['confirm'] != '0']
            confirmed_count = len(df_confirmed)
            if confirmed_count >= n:
                break
        else:
            total_count = len(df_temp)
            if total_count >= n:
                break

        # 如果返回的数据少于请求的数量，说明已经没有更多数据了
        # 但此时可能还没有足够的确认K线，所以继续检查，让后续逻辑处理
        if len(res) < batch_size:
            # 如果已经没有更多数据，但确认K线还不够，会在最后抛出异常
            break

    # 去重并按时间排序
    df = pd.DataFrame(all_klines,
                      columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'confirm'])
    df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

    # 如果需要排除未确认的K线
    if exclude_unconfirmed_bar:
        df = df[df['confirm'] != '0']

    # 确保返回正好n条数据（取最后n条，因为数据是按时间正序排列的，最后n条是最接近结束时间的）
    if len(df) < n:
        raise ValueError(f"历史数据不足: 请求{n}条K线，但只获取到{len(df)}条")
    
    # 返回正好n条数据
    df = df.tail(n).reset_index(drop=True)

    df.drop(columns=['confirm'], inplace=True)
    return df


async def get_klines_start_from_specify_time(inst_id: str, start_date: str, interval_minutes=60, n=200, exclude_last_bar=False) -> pd.DataFrame:
    now = comon_utils.get_timestamp(str(datetime.now().replace(microsecond=0)))
    start_timestamp = comon_utils.get_timestamp(start_date)

    all_klines = []
    remaining = n

    while remaining > 0:
        # OKX API 限制每次最多返回 200 条数据
        batch_size = min(remaining, 200)
        res = marketAPI.get_candlesticks(
            instId=inst_id,
            before=start_timestamp,
            after=now,
            bar=get_bar_size(interval_minutes),
            limit=batch_size
        )['data']

        if not res:
            break

        # 处理当前批次的数据
        batch_klines = []
        for line in res:
            line[0] = str(datetime.fromtimestamp(int(line[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S'))
            batch_klines.append([line[0], line[1], line[2], line[3], line[4], line[5], line[8]])

        # 添加到总数据中
        all_klines.extend(batch_klines)

        # 如果返回的数据少于请求的数量，说明已经没有更多数据了
        if len(res) < batch_size:
            break
        else:
            raise Exception("Invalid data")

    # 去重并按时间排序
    df = pd.DataFrame(all_klines,
                      columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'confirm'])
    df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

    # 如果需要排除最后一个未完成的K线
    if exclude_last_bar:
        df = df[:-1]

    return df



async def get_klines(inst_id: str, interval_minutes=60, n=200,
                     exclude_unconfirmed_bar=False,
                     end_timestamp: str = None) -> pd.DataFrame:
    if end_timestamp:
        now = end_timestamp
    else:
        now = publicAPI.get_system_time()['data'][0]['ts']

    all_klines = []
    remaining = n
    current_end = now

    while remaining > 0:
        # OKX API 限制每次最多返回 200 条数据
        batch_size = min(remaining, 200)
        shift_time = move_time_backward(current_end, interval_minutes, batch_size)

        res = marketAPI.get_candlesticks(
            instId=inst_id,
            before=shift_time,
            after=current_end,
            bar=get_bar_size(interval_minutes),
            limit=batch_size
        )['data']

        if not res:
            break

        # 处理当前批次的数据
        batch_klines = []
        for line in res:
            line[0] = str(datetime.fromtimestamp(int(line[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S'))
            # line[0] = str(datetime.fromtimestamp(int(line[0]) / 1000).strftime('%m-%d %H:%M:%S'))
            batch_klines.append([line[0], line[1], line[2], line[3], line[4], line[5], line[8]])

        # 添加到总数据中
        all_klines.extend(batch_klines)

        # 更新剩余数量和下次查询的结束时间
        remaining -= len(res)
        # 设置下一批次的结束时间为最后一条数据的时间
        if res:
            current_end = shift_time

        # 如果返回的数据少于请求的数量，说明已经没有更多数据了
        if len(res) < batch_size:
            break

    # 去重并按时间排序
    df = pd.DataFrame(all_klines,
                      columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'confirm'])
    df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

    # 如果需要排除最后一个未完成的K线
    if exclude_unconfirmed_bar:
        df = df[df['confirm'] != '0']

    df.drop(columns=['confirm'], inplace=True)

    return df


def get_position():
    result = accountAPI.get_positions()['data']
    tickets = []
    for i in result:
        pos_id = i["posId"]
        inst_id = i["instId"]
        pos_side = "short" if float(i["pos"]) < 0 else "long"
        avg_px = (i["avgPx"])
        liq_px = i["liqPx"]
        upl = str(round(float(i["upl"]), 2))
        upl_ratio = f"{round(float(i["uplRatio"]) * 100, 4)}%"
        be_px = i["bePx"]
        lever = i["lever"]
        c_time = int(i["cTime"])
        create_time = get_date(c_time)
        tickets.append(Ticket(
            # pos_id=pos_id,
            inst_id=inst_id,
            pos_side=pos_side,
            avg_px=avg_px,
            liq_px=liq_px,
            upl=upl,
            upl_ratio=upl_ratio,
            be_px=be_px,
            lever=lever,
            create_time=create_time
        ))
    return tickets


# 精英交易员合约多空持仓仓位比
async def get_top_trader_position_ratio(inst_id, period):
    params = {
        'instId': inst_id,
        "period": period
    }
    endpoint = '/api/v5/rubik/stat/contracts/long-short-position-ratio-contract-top-trader'
    headers = _create_headers('GET', endpoint, params)
    url = f"https://www.okx.com{endpoint}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        data = data['data']
        data = sorted(data, key=lambda x: x[0])
        results = []
        for d in data:
            date_time = comon_utils.get_date(int(d[0]))
            ratio = round(float(d[1]), 4)
            results.append([date_time, ratio])
        return results


# 精英交易员合约多空持仓人数比
async def get_top_trader_account_ratio(inst_id, period):
    params = {
        'instId': inst_id,
        "period": period
    }
    endpoint = '/api/v5/rubik/stat/contracts/long-short-account-ratio-contract-top-trader'
    headers = _create_headers('GET', endpoint, params)
    url = f"https://www.okx.com{endpoint}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        data = data['data']
        data = sorted(data, key=lambda x: x[0])
        results = []
        for d in data:
            date_time = comon_utils.get_date(int(d[0]))
            ratio = round(float(d[1]), 4)
            results.append([date_time, ratio])
        return results


async def get_account_balance():
    result = accountAPI.get_account_balance(ccy="USDT")
    available_usdt = result['data'][0]["details"][0]["availBal"]
    return round(float(available_usdt), 2)


if __name__ == '__main__':
    import asyncio

    # result = asyncio.run(get_klines_end_with_specify_time("BTC-USDT-SWAP", "2026-01-09 22:35:01", 5, 200,True))
    # print(result.tail())
    # res = get_position()
    # print(res)
    # res = get_position_history("SOL-USDT-SWAP", "", "")
    # print(res[:3])
    # res = asyncio.run(get_top_trader_account_ratio("DOGE-USDT-SWAP", "15m"))
    # print(res)
    # res = asyncio.run(get_top_trader_position_ratio("DOGE-USDT-SWAP", "15m"))
    # print(res)
    # print(get_account_balance())
    # res = place_algo_order("ETH-USDT-SWAP", "sell", "1", "3250", "3000", "3300")
    # print(res)
    # get_pending_algo_order_id()
    # print(cancel_algo_order("ETH-USDT-SWAP"))
    # modify_algo_order("ETH-USDT-SWAP", "3070396836683882496", "3005.49", "2903.01")
    # result = tradeAPI.order_algos_list(ordType="conditional")
    # print(result)
    # import asyncio
    # now = datetime.now()
    # result = now.replace(
    #     minute=(now.minute // 15) * 15,
    #     second=0,
    #     microsecond=0
    # )
    # result = result - timedelta(minutes=1)
    # result = asyncio.run(get_klines_start_from_specify_time("ETH-USDT-SWAP", str(result)))
    # print(result.tail(100))
