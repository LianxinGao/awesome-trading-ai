from client import ok_client
import talib


async def get_kline_with_ema(inst_id, interval, limit, precision, exclude_unconfirmed_bar = True):
    klines = await ok_client.get_klines(inst_id, interval, limit, exclude_unconfirmed_bar= exclude_unconfirmed_bar)

    name = f'ema21'
    klines['close'] = klines['close'].astype(float)
    ema21 = talib.EMA(klines["close"], timeperiod=21)
    ema21 = ema21.round(precision)
    klines[name] = ema21
    klines.dropna(subset=[name], inplace=True)
    return klines


if __name__ == '__main__':
    import asyncio

    result = asyncio.run(get_kline_with_ema('BTC-USDT-SWAP', 15, 300, 2))
    print(result.tail())