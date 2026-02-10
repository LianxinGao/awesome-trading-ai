import pandas as pd
import numpy as np
import talib
from sklearn.linear_model import LinearRegression

class UltimateMarketClassifier:
    """
    基于阿尔布鲁克斯 (Al Brooks) 价格行为 (Price Action) 理论的市场周期分类器。
    市场周期核心循环：Breakout (Spike) -> Tight Channel -> Broad Channel -> Trading Range
    """

    def __init__(self):
        pass

    def get_single_mode(self, df, 
                       window=20,
                       ema_period=21,
                       swing_window=3):
        """
        判断当前市场模式
        
        :param df: 包含 open, high, low, close 的 DataFrame
        :param window: 分析的窗口大小
        :param ema_period: EMA 周期，默认20
        :param swing_window: 识别波段高低点的局部窗口
        :return: 市场模式字符串
        """
        # 1. 数据预处理
        df = self._prepare_data(df)
        if len(df) < window + 5:  # 需要稍微多一点数据计算指标
            return "INIT"

        # 提取当前分析窗口
        subset = df.iloc[-window:].copy()
        actual_window = len(subset)

        # 2. 计算价格行为基础指标 (Bar Characteristics)
        pa_features = self._calculate_pa_features(subset, df, ema_period)
        
        # 3. 识别波段高低点 (Swing Points)
        swing_trends = self._analyze_swing_trends(subset, swing_window)
        
        # 4. 线性回归分析 (拟合度与斜率)
        regression = self._calculate_regression(subset)

        # 5. 模式判定逻辑 (按照 Al Brooks 优先级)
        
        # --- A. BREAKOUT (SPIKE) 判定 ---
        # 特征：连续强趋势棒，几乎无重叠，跳空，或远离 EMA
        if self._is_breakout(pa_features, subset):
            direction = "Bull" if pa_features['last_bars_direction'] > 0 else "Bear"
            return f"Breakout ({direction})"

        # --- B. TIGHT CHANNEL 判定 ---
        # 特征：强趋势但有微小重叠，价格维持在 EMA 一侧且不触碰，回撤极浅
        if self._is_tight_channel(pa_features, regression, subset):
            direction = "Bull" if regression['slope'] > 0 else "Bear"
            return f"Tight Channel ({direction})"

        # --- C. BROAD CHANNEL 判定 ---
        # 特征：有明确的趋势高低点 (HH/HL 或 LH/LL)，但回撤深（经常触碰或穿过 EMA），重叠多
        if self._is_broad_channel(swing_trends, pa_features, regression):
            direction = "Bull" if regression['slope'] > 0 else "Bear"
            return f"Broad Channel ({direction})"

        # --- D. TRADING RANGE 判定 ---
        # 特征：高低点无序，价格在 EMA 上下交织，K线阴阳交替，重叠极大
        return "Trading Range"

    def _prepare_data(self, df):
        df = df.copy()
        cols = ['open', 'high', 'low', 'close']
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=cols)

    def _calculate_pa_features(self, subset, full_df, ema_period):
        """计算 K 线形态和买卖压力特征"""
        # 基础计算
        close = subset['close']
        open_p = subset['open']
        high = subset['high']
        low = subset['low']
        
        body = close - open_p
        abs_body = body.abs()
        bar_range = (high - low).replace(0, 1e-9)
        body_ratio = abs_body / bar_range  # 实体占比
        
        # 1. 趋势棒识别 (Al Brooks: 实体占全长 50% 以上)
        is_trend_bar = body_ratio > 0.5
        is_bull_trend = is_trend_bar & (body > 0)
        is_bear_trend = is_trend_bar & (body < 0)
        
        # 2. 连续性分析 (最近 3-5 根 K 线)
        last_3_bars = body.iloc[-3:]
        last_3_bull = (last_3_bars > 0).all()
        last_3_bear = (last_3_bars < 0).all()
        
        # 3. K线重叠率 (Bar Overlap)
        prev_high = subset['high'].shift(1)
        prev_low = subset['low'].shift(1)
        overlap_h = np.minimum(high, prev_high)
        overlap_l = np.maximum(low, prev_low)
        overlap_range = (overlap_h - overlap_l).clip(lower=0)
        avg_overlap = (overlap_range / bar_range).mean()
        
        # 4. EMA 交互
        ema = talib.EMA(full_df['close'], timeperiod=ema_period)
        subset_ema = ema.loc[subset.index]
        
        ema_dist = (close - subset_ema).abs() / (subset_ema + 1e-9)
        ema_touch_ratio = ((low <= subset_ema) & (high >= subset_ema)).sum() / len(subset)
        wrong_side_ratio = ((close > subset_ema) if body.mean() < 0 else (close < subset_ema)).sum() / len(subset)

        # 5. 买卖压力
        bull_pressure = abs_body[body > 0].sum()
        bear_pressure = abs_body[body < 0].sum()
        pressure_ratio = bull_pressure / (bear_pressure + 1e-9)

        return {
            'last_3_bull': last_3_bull,
            'last_3_bear': last_3_bear,
            'avg_overlap': avg_overlap,
            'ema_touch_ratio': ema_touch_ratio,
            'wrong_side_ratio': wrong_side_ratio,
            'pressure_ratio': pressure_ratio,
            'last_bars_direction': 1 if body.iloc[-1] > 0 else -1,
            'body_ratio_last': body_ratio.iloc[-1],
            'ema_dist_last': ema_dist.iloc[-1]
        }

    def _analyze_swing_trends(self, subset, swing_window):
        """识别波段高低点趋势"""
        # 简单的局部极值识别
        rolling_high = subset['high'].rolling(window=swing_window, center=True).max()
        rolling_low = subset['low'].rolling(window=swing_window, center=True).min()
        
        sw_highs = subset['high'][subset['high'] == rolling_high].values
        sw_lows = subset['low'][subset['low'] == rolling_low].values
        
        is_hh = len(sw_highs) >= 2 and sw_highs[-1] > sw_highs[-2]
        is_hl = len(sw_lows) >= 2 and sw_lows[-1] > sw_lows[-2]
        is_lh = len(sw_highs) >= 2 and sw_highs[-1] < sw_highs[-2]
        is_ll = len(sw_lows) >= 2 and sw_lows[-1] < sw_lows[-2]
        
        return {
            'bull_trend': is_hh and is_hl,
            'bear_trend': is_lh and is_ll,
            'has_swings': len(sw_highs) >= 2 and len(sw_lows) >= 2
        }

    def _calculate_regression(self, subset):
        """计算线性回归特征"""
        y = (subset['close'].values / subset['close'].iloc[0]) - 1
        x = np.arange(len(y)).reshape(-1, 1)
        reg = LinearRegression().fit(x, y.reshape(-1, 1))
        
        return {
            'r2': reg.score(x, y.reshape(-1, 1)),
            'slope': reg.coef_[0][0]
        }

    def _is_breakout(self, pa, subset):
        """Breakout 判定逻辑"""
        # 1. 连续 3 根强趋势棒
        if pa['last_3_bull'] or pa['last_3_bear']:
            return True
        # 2. 单根极强 K 线且远离 EMA (Spike)
        if pa['body_ratio_last'] > 0.8 and pa['ema_dist_last'] > 0.005:
            return True
        return False

    def _is_tight_channel(self, pa, reg, subset):
        """Tight Channel 判定逻辑"""
        # 1. R2 较高且重叠率低
        # 2. 价格极少触碰 EMA (EMA 磁吸失效)
        # 3. 买卖压力呈现压倒性
        is_trending = reg['r2'] > 0.7 and abs(reg['slope']) > 0.0005
        low_overlap = pa['avg_overlap'] < 0.35
        ema_avoidance = pa['ema_touch_ratio'] < 0.2
        strong_pressure = pa['pressure_ratio'] > 2.5 or pa['pressure_ratio'] < 0.4
        
        return is_trending and (low_overlap or ema_avoidance) and strong_pressure

    def _is_broad_channel(self, swings, pa, reg):
        """Broad Channel 判定逻辑"""
        # 1. 必须有高低点趋势 (HH/HL 或 LH/LL)
        # 2. 或者 R2 尚可且有一定斜率
        if swings['bull_trend'] or swings['bear_trend']:
            return True
        
        # 如果拟合度一般但仍有明显重心移动
        if reg['r2'] > 0.4 and abs(reg['slope']) > 0.0003:
            # 宽通道允许频繁触碰 EMA 和高重叠
            return True
            
        return False

def convert_ohlc_to_numeric(df):
    """辅助函数：确保数据格式正确"""
    ohlc_columns = ['open', 'high', 'low', 'close']
    for col in ohlc_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

if __name__ == '__main__':
    # 示例运行逻辑 (保持原有测试框架)
    from client import ok_client
    import asyncio

    end_date = "2026-02-09 23:45:01"
    try:
        df_15m = asyncio.run(ok_client.get_klines_end_with_specify_time('BTC-USDT-SWAP', end_date, 5, 200, True))
        df_15m = convert_ohlc_to_numeric(df_15m)
        
        classifier = UltimateMarketClassifier()
        
        for w in [20, 40, 60, 80]:
            state = classifier.get_single_mode(df_15m, window=w)
            print(f"Window {w}: {state}")
    except Exception as e:
        print(f"Error during execution: {e}")
