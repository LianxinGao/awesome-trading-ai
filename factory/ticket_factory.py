from client import ok_client
from client.ok_models import Ticket
from datetime import datetime


def get_timestamp(date):
    return int(datetime.strptime(date, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

def get_ticket_data()->list[Ticket]:
    tickets = ok_client.get_position()
    return tickets

def cancel_order(inst_id):
    order_id = get_pending_order_id(inst_id)
    result = ok_client.cancel_order(inst_id, order_id)
    print(result)

def get_pending_order_id(inst_id):
    order_id = ok_client.get_pending_order(inst_id)
    return order_id

def close_position(inst_id):
    result = ok_client.close_position(inst_id, ok_client.TdMode.CROSS)
    print(result)

def order_position(inst_id, side, sz, tp_trigger_px, sl_trigger_px, entry_price = ""):
    if not entry_price:
        result = ok_client.place_order(
            order_type=ok_client.OrderType.OPTIMAL_LIMIT_LOC,
            inst_id=inst_id,
            side=side,
            sz=sz,
            tp_trigger_px=tp_trigger_px,
            sl_trigger_px=sl_trigger_px,
            td_mode=ok_client.TdMode.CROSS
        )
    else:
        result = ok_client.place_order(
            order_type=ok_client.OrderType.LIMIT,
            inst_id=inst_id,
            side=side,
            sz=sz,
            tp_trigger_px=tp_trigger_px,
            sl_trigger_px=sl_trigger_px,
            px=entry_price,
            td_mode=ok_client.TdMode.CROSS
        )
    return result

def order_algo_order(inst_id, side, sz, trigger_px, tp_trigger_px, sl_trigger_px):
    result = ok_client.place_algo_order(inst_id, side, sz, trigger_px, tp_trigger_px, sl_trigger_px)
    return result

def cancel_algo_order(inst_id):
    algo_order_id = ok_client.get_pending_algo_order_id()
    result = ''
    if algo_order_id:
        result = ok_client.cancel_algo_order(inst_id, algo_order_id)
    return result

def evaluate_trade(inst_id, begin, end):
    begin = str(get_timestamp(begin))
    end = str(get_timestamp(end))

    completed_tickets = ok_client.get_position_history(inst_id, begin, end)
    total_trade = 0
    win_trade = 0
    unrealized_pnl = 0
    fee = 0
    realized_pnl = 0

    for ticket in completed_tickets:
        total_trade += 1
        if ticket.pnl > 0:
            win_trade += 1
        realized_pnl += ticket.realized_pnl
        unrealized_pnl += ticket.pnl
        fee += ticket.fee

    win_rate = win_trade / total_trade if total_trade > 0 else 0
    avg_pnl = realized_pnl / total_trade if total_trade > 0 else 0
    json_data = {
        "总交易数": total_trade,
        "总胜数": win_trade,
        "总胜率": f"{win_rate:.2%}" if total_trade > 0 else "0.00%",
        "总盈亏": f"{realized_pnl:.2f} USDT",
        "平均每笔盈亏": f"{avg_pnl:.2f} USDT"
        }
    return json_data

if __name__ == '__main__':
    # inst_id = "ETH-USDT-SWAP"
    # res = order_position(inst_id, "sell", "1", "2.82", "2.84", entry_price="2.83")
    # print(res)
    # result = cancel_algo_order(inst_id)
    # print(result)
    res = get_ticket_data()
    print(res)
    eval_result = evaluate_trade("BTC-USDT-SWAP", "2026-01-03 13:35:00", end = str(datetime.now().replace(microsecond=0)))
    print(eval_result)
    # res = order_position(inst_id, "buy", sz, 2.87, 2.86)
    # print(res)