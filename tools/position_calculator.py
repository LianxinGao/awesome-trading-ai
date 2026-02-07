from client import ok_client
import math

OK_TRADE_FEE = 0.0005


async def cal_contract_size(usdt_risk_amount, symbol, entry_price, stop_loss_price):
    contract_val, contract_mult, min_sz = await ok_client.get_swap_contract_info_local(symbol)

    unit_coin_amount = contract_val * contract_mult
    price_diff = abs(entry_price - stop_loss_price)
    loss_per_contract = price_diff * unit_coin_amount

    open_fee_per_contract = entry_price * unit_coin_amount * OK_TRADE_FEE
    close_fee_per_contract = stop_loss_price * unit_coin_amount * OK_TRADE_FEE
    total_fee_per_contract = open_fee_per_contract + close_fee_per_contract

    total_risk_cost_per_contract = loss_per_contract + total_fee_per_contract

    if total_risk_cost_per_contract == 0:
        # 这种情况通常不应该发生，除非止损=入场且费率为0
        contract_size = 0
    else:
        contract_size = usdt_risk_amount / total_risk_cost_per_contract

    if contract_size < min_sz:
        contract_size = min_sz  # 或者这里可以选择 return 0 表示放弃交易
    else:
        # 向下取整到 min_sz 的整数倍
        contract_size = math.floor(contract_size / min_sz) * min_sz

    return contract_val, contract_size, contract_mult


async def cal_trade_fee_and_profit_and_sz(symbol, usdt_amount, entry_price, take_profit_price, stop_loss_price):
    """
    计算交易手续费、利润和仓位大小

    Args:
        symbol: 交易对
        usdt_amount: USDT 金额（本金）
        entry_price: 入场价格
        take_profit_price: 目标价格
        stop_loss_price: 止损价格

    Returns:
        tuple: (open_fee, close_fee, take_profit_value, sz, c_val, c_mult)
    """
    assert isinstance(symbol, str)
    assert isinstance(usdt_amount, (float, int))
    assert isinstance(entry_price, (float, int))
    assert isinstance(take_profit_price, (float, int))
    assert isinstance(stop_loss_price, (float, int))

    c_val, sz, c_mult = await cal_contract_size(usdt_amount, symbol, entry_price, stop_loss_price)
    open_fee = OK_TRADE_FEE * c_val * sz * entry_price
    close_fee = OK_TRADE_FEE * c_val * sz * take_profit_price
    take_profit_value = abs(take_profit_price - entry_price) * sz * c_val

    return open_fee, close_fee, take_profit_value, sz, c_val, c_mult
