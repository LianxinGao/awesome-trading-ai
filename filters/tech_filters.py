import pandas as pd
from datetime import datetime, timedelta
import talib
import numpy as np
import traceback

interval_period_map = {
    15: '15m',
    60: '1h'
}


def _detect_pattern(pattern_func, name, description, open_prices, high_prices, low_prices, close_prices):
    """检测单个形态并返回结果"""
    pattern_result = pattern_func(open_prices, high_prices, low_prices, close_prices)
    patterns = []
    for value in pattern_result:
        if value != 0:
            patterns.append({
                'name': name,
                'description': description,
                'direction': 'BUY' if value > 0 else 'SELL'
            })
    return patterns


def _detect_three_consecutive_bullish(open_prices, high_prices, low_prices, close_prices, body_ratio_threshold=0.4):
    """检测三个连续上涨的K线"""
    patterns = []
    if len(open_prices) < 3:
        return patterns

    for i in range(len(open_prices) - 2):
        # 检查连续三根K线
        k1_open, k1_close = open_prices[i], close_prices[i]
        k2_open, k2_close = open_prices[i + 1], close_prices[i + 1]
        k3_open, k3_close = open_prices[i + 2], close_prices[i + 2]

        # 检查是否都是阳线（收盘价 > 开盘价）
        is_bullish_1 = k1_close > k1_open
        is_bullish_2 = k2_close > k2_open
        is_bullish_3 = k3_close > k3_open

        if not (is_bullish_1 and is_bullish_2 and is_bullish_3):
            continue

        # 计算每根K线的实体占比
        k1_body = abs(k1_close - k1_open)
        k1_total = high_prices[i] - low_prices[i]
        k2_body = abs(k2_close - k2_open)
        k2_total = high_prices[i + 1] - low_prices[i + 1]
        k3_body = abs(k3_close - k3_open)
        k3_total = high_prices[i + 2] - low_prices[i + 2]

        # 检查实体占比是否满足要求
        if k1_total > 0 and k2_total > 0 and k3_total > 0:
            ratio1 = k1_body / k1_total
            ratio2 = k2_body / k2_total
            ratio3 = k3_body / k3_total

            if ratio1 >= body_ratio_threshold and ratio2 >= body_ratio_threshold and ratio3 >= body_ratio_threshold:
                patterns.append({
                    'name': 'CUSTOM_3CONSECUTIVE_BULLISH (三连阳)',
                    'description': f'连续三根上涨K线，每根实体占比≥{body_ratio_threshold:.0%}',
                    'direction': 'BUY'
                })

    return patterns


def _detect_three_consecutive_bearish(open_prices, high_prices, low_prices, close_prices, body_ratio_threshold=0.4):
    """检测三个连续下跌的K线"""
    patterns = []
    if len(open_prices) < 3:
        return patterns

    for i in range(len(open_prices) - 2):
        # 检查连续三根K线
        k1_open, k1_close = open_prices[i], close_prices[i]
        k2_open, k2_close = open_prices[i + 1], close_prices[i + 1]
        k3_open, k3_close = open_prices[i + 2], close_prices[i + 2]

        # 检查是否都是阴线（收盘价 < 开盘价）
        is_bearish_1 = k1_close < k1_open
        is_bearish_2 = k2_close < k2_open
        is_bearish_3 = k3_close < k3_open

        if not (is_bearish_1 and is_bearish_2 and is_bearish_3):
            continue

        # 计算每根K线的实体占比
        k1_body = abs(k1_close - k1_open)
        k1_total = high_prices[i] - low_prices[i]
        k2_body = abs(k2_close - k2_open)
        k2_total = high_prices[i + 1] - low_prices[i + 1]
        k3_body = abs(k3_close - k3_open)
        k3_total = high_prices[i + 2] - low_prices[i + 2]

        # 检查实体占比是否满足要求
        if k1_total > 0 and k2_total > 0 and k3_total > 0:
            ratio1 = k1_body / k1_total
            ratio2 = k2_body / k2_total
            ratio3 = k3_body / k3_total

            if ratio1 >= body_ratio_threshold and ratio2 >= body_ratio_threshold and ratio3 >= body_ratio_threshold:
                patterns.append({
                    'name': 'CUSTOM_3CONSECUTIVE_BEARISH (三连阴)',
                    'description': f'连续三根下跌K线，每根实体占比≥{body_ratio_threshold:.0%}',
                    'direction': 'SELL'
                })

    return patterns


def filter_by_patterns(df: pd.DataFrame, n_klines: int, action: str, pattern_type='all',
                       body_ratio_threshold=0.4):
    try:
        if df.empty or len(df) < 3:
            return {
                'patterns': [],
                'count': 0,
                'has_conflict': False,
                'direction_match': False
            }

        # 确保数据按时间正序排列（talib需要）
        df = df.sort_values('timestamp').reset_index(drop=True)

        # 只取最后n_klines根K线
        df = df.tail(n_klines).reset_index(drop=True)

        # 转换为numpy数组（talib需要）
        open_prices = df['open'].values.astype(np.float64)
        high_prices = df['high'].values.astype(np.float64)
        low_prices = df['low'].values.astype(np.float64)
        close_prices = df['close'].values.astype(np.float64)

        # 检测到的形态列表
        detected_patterns = []

        # 标准化pattern_type参数
        if isinstance(pattern_type, str):
            pattern_type = pattern_type.lower()
            # 将字符串 '1', '2', '3' 转换为整数
            if pattern_type == '1':
                pattern_type = 1
            elif pattern_type == '2':
                pattern_type = 2
            elif pattern_type == '3':
                pattern_type = 3

        # 判断需要检测哪些类型的形态
        detect_1line = (pattern_type == 'all' or pattern_type == 1)
        detect_2line = (pattern_type == 'all' or pattern_type == 2)
        detect_3line = (pattern_type == 'all' or pattern_type == 3)

        # ========== 一、单根K线形态 (1 Line Patterns) ==========
        if detect_1line:
            detected_patterns.extend(
                _detect_pattern(talib.CDLHAMMER, 'CDLHAMMER (锤头线)', '底部反转信号，实体小，下影线长', open_prices,
                                high_prices, low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDLHANGINGMAN, 'CDLHANGINGMAN (上吊线)', '顶部反转信号，出现在上涨趋势中',
                                open_prices, high_prices, low_prices, close_prices))
            detected_patterns.extend(_detect_pattern(talib.CDLSHOOTINGSTAR, 'CDLSHOOTINGSTAR (流星线/射击之星)',
                                                     '顶部反转信号，实体小，上影线长', open_prices, high_prices,
                                                     low_prices, close_prices))
            detected_patterns.extend(_detect_pattern(talib.CDLINVERTEDHAMMER, 'CDLINVERTEDHAMMER (倒锤头线)',
                                                     '底部反转信号，出现在下跌趋势中', open_prices, high_prices,
                                                     low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDLDOJI, 'CDLDOJI (十字星)', '市场犹豫不决，多空平衡，变盘点', open_prices,
                                high_prices, low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDLMARUBOZU, 'CDLMARUBOZU (光头光脚/大阳大阴)', '强烈的单边趋势，没有影线',
                                open_prices, high_prices, low_prices, close_prices))

        # ========== 二、两根K线形态 (2 Line Patterns) ==========
        if detect_2line:
            detected_patterns.extend(_detect_pattern(talib.CDLENGULFING, 'CDLENGULFING (吞噬形态/抱线)',
                                                     '极强的反转信号，第二根K线实体完全包住第一根', open_prices,
                                                     high_prices, low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDLHARAMI, 'CDLHARAMI (孕线)', '变盘信号，第一根大实体包住第二根小实体',
                                open_prices, high_prices, low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDLPIERCING, 'CDLPIERCING (刺透形态/斩回线)', '底部看涨，大阴线后大阳线低开高走',
                                open_prices, high_prices, low_prices, close_prices))
            detected_patterns.extend(_detect_pattern(talib.CDLDARKCLOUDCOVER, 'CDLDARKCLOUDCOVER (乌云盖顶)',
                                                     '顶部看跌，大阳线后大阴线高开低走', open_prices, high_prices,
                                                     low_prices, close_prices))

        # ========== 三、三根K线形态 (3 Line Patterns) ==========
        if detect_3line:
            detected_patterns.extend(_detect_pattern(talib.CDLMORNINGSTAR, 'CDLMORNINGSTAR (早晨之星/启明星)',
                                                     '强烈的底部反转，大阴线+小K线跳空低开+大阳线回补', open_prices,
                                                     high_prices, low_prices, close_prices))
            detected_patterns.extend(_detect_pattern(talib.CDLEVENINGSTAR, 'CDLEVENINGSTAR (黄昏之星)',
                                                     '强烈的顶部反转，大阳线+小K线跳空高开+大阴线回补', open_prices,
                                                     high_prices, low_prices, close_prices))
            detected_patterns.extend(_detect_pattern(talib.CDL3WHITESOLDIERS, 'CDL3WHITESOLDIERS (红三兵/白三兵)',
                                                     '强烈的上涨趋势，连续三根阳线收盘价依次创新高', open_prices,
                                                     high_prices, low_prices, close_prices))
            detected_patterns.extend(_detect_pattern(talib.CDL3BLACKCROWS, 'CDL3BLACKCROWS (三只乌鸦)',
                                                     '强烈的下跌趋势，连续三根阴线收盘价依次创新低', open_prices,
                                                     high_prices, low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDL3INSIDE, 'CDL3INSIDE (三内部形态)', '孕线的确认形态，孕线+第三根确认线',
                                open_prices, high_prices, low_prices, close_prices))
            detected_patterns.extend(
                _detect_pattern(talib.CDL3OUTSIDE, 'CDL3OUTSIDE (三外部形态)', '吞噬形态的确认形态，吞噬+第三根确认线',
                                open_prices, high_prices, low_prices, close_prices))

        # ========== 自定义形态检测 ==========
        detected_patterns.extend(
            _detect_three_consecutive_bullish(open_prices, high_prices, low_prices, close_prices, body_ratio_threshold))
        detected_patterns.extend(
            _detect_three_consecutive_bearish(open_prices, high_prices, low_prices, close_prices, body_ratio_threshold))

        count = len(detected_patterns)

        # 检查是否存在冲突（同时存在BUY和SELL形态）
        has_bullish = any(p['direction'] == 'BUY' for p in detected_patterns)
        has_bearish = any(p['direction'] == 'SELL' for p in detected_patterns)
        has_conflict = has_bullish and has_bearish

        # 检查检测到的形态方向是否与strategy方向一致
        # action固定为'BUY'或'SELL'
        direction_match = any(p['direction'] == action for p in detected_patterns)

        return {
            'patterns': detected_patterns,
            'count': count,
            'has_conflict': has_conflict,
            'direction_match': direction_match
        }

    except Exception as e:
        traceback.print_exc()
        return {
            'patterns': [],
            'count': 0,
            'has_conflict': True,
            'direction_match': False
        }


def filter_by_atr_distance(df:pd.DataFrame, window_size: int, entry_price: float, take_profit_price: float, ratio: float, atr_period = 14):

    required_klines = window_size + atr_period

    try:
        if df.empty or len(df) < required_klines:
            return {
                'passed': False,
                'distance': abs(take_profit_price - entry_price),
                'avg_atr': 0.0,
                'required_distance': 0.0,
                'ratio_actual': 0.0,
                'error': f'数据不足，需要至少{required_klines}根K线，实际只有{len(df)}根'
            }

        # 确保数据按时间正序排列
        df = df.sort_values('timestamp').reset_index(drop=True)

        # 转换为numpy数组（talib需要）
        high_prices = df['high'].values.astype(np.float64)
        low_prices = df['low'].values.astype(np.float64)
        close_prices = df['close'].values.astype(np.float64)

        # 计算所有K线的ATR（使用14周期）
        atr_values = talib.ATR(high_prices, low_prices, close_prices, timeperiod=atr_period)

        # 取最后window_size个ATR值（这些是最后window_size根K线的ATR）
        # 过滤掉NaN值
        last_window_atr = atr_values[-window_size:]
        valid_atr = last_window_atr[~np.isnan(last_window_atr)]

        if len(valid_atr) == 0:
            return {
                'passed': False,
                'distance': abs(take_profit_price - entry_price),
                'avg_atr': 0.0,
                'required_distance': 0.0,
                'ratio_actual': 0.0,
                'error': '无法计算ATR，最后window_size根K线的ATR值均为NaN'
            }

        # 计算平均ATR
        avg_atr = float(np.mean(valid_atr))

        # 计算入场价到止盈价的距离
        distance = abs(take_profit_price - entry_price)

        # 计算所需的最小距离
        required_distance = ratio * avg_atr

        # 判断是否满足条件
        passed = distance > required_distance

        # 计算实际倍数
        ratio_actual = distance / avg_atr if avg_atr > 0 else 0.0

        return {
            'passed': passed,
            'distance': distance,
            'avg_atr': avg_atr,
            'required_distance': required_distance,
            'ratio_actual': ratio_actual
        }

    except Exception as e:
        traceback.print_exc()
        return {
            'passed': False,
            'distance': abs(take_profit_price - entry_price),
            'avg_atr': 0.0,
            'required_distance': 0.0,
            'ratio_actual': 0.0,
            'error': str(e)
        }


if __name__ == '__main__':
    test_date = datetime.strptime('2026-01-22 11:00:00', '%Y-%m-%d %H:%M:%S')
    result = filter_by_patterns('SOL-USDT-SWAP', test_date, 15, 15, )
    print(result)
