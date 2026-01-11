from client import ok_client
import talib


async def get_kline_with_ema(klines, precision):
    name = f'ema21'
    ema21 = talib.EMA(klines["close"], timeperiod=21)
    ema21 = ema21.round(precision)
    klines[name] = ema21
    klines.dropna(subset=[name], inplace=True)
    return klines


def get_kline_with_ema_analysis(klines, precision):
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