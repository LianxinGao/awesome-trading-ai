import pandas as pd
import numpy as np
import talib
from sklearn.linear_model import LinearRegression


class UltimateMarketClassifier:
    def __init__(self):
        """市场周期分类器，所有参数在调用时配置"""
        pass

    def get_single_mode(self, df,
                       window=20,
                       z_threshold=1.5,
                       min_data_points=10,
                       min_window=5,
                       # Breakout相关参数
                       breakout_z_high_score=3,
                       breakout_z_medium_score=2,
                       breakout_z_medium_ratio=0.7,
                       breakout_adx_high=20,
                       breakout_adx_high_score=2,
                       breakout_adx_medium=15,
                       breakout_adx_medium_score=1,
                       breakout_price_change_pct=0.05,
                       breakout_price_change_score=1,
                       breakout_score_threshold=4,
                       # Channel相关参数
                       channel_r2_high=0.65,
                       channel_r2_high_score=3,
                       channel_r2_medium=0.5,
                       channel_r2_medium_score=2,
                       channel_slope_high=0.001,
                       channel_slope_high_score=2,
                       channel_slope_medium=0.0005,
                       channel_slope_medium_score=1,
                       channel_adx_high=25,
                       channel_adx_high_score=2,
                       channel_adx_medium=18,
                       channel_adx_medium_score=1,
                       channel_score_threshold_high=5,
                       channel_score_threshold_low=3,
                       channel_r2_min=0.4,
                       # Tight/Broad Channel区分参数
                       tight_channel_r2_threshold=0.75,
                       tight_channel_volatility_threshold=0.02):
        """
        判断市场周期模式
        
        :param df: 包含 open, high, low, close 列的DataFrame，可以是任意数量
        
        :param window: 计算周期，默认20
        :param z_threshold: Z-Score阈值，默认1.5
        :param min_data_points: 最小数据点要求，默认10
        :param min_window: 最小窗口大小，默认5
        
        :param breakout_z_high_score: Breakout的Z-Score高分得分，默认3
        :param breakout_z_medium_score: Breakout的Z-Score中等得分，默认2
        :param breakout_z_medium_ratio: Breakout的Z-Score中等阈值比例，默认0.7
        :param breakout_adx_high: Breakout的ADX高分阈值，默认20
        :param breakout_adx_high_score: Breakout的ADX高分得分，默认2
        :param breakout_adx_medium: Breakout的ADX中等阈值，默认15
        :param breakout_adx_medium_score: Breakout的ADX中等得分，默认1
        :param breakout_price_change_pct: Breakout的价格变化百分比阈值，默认0.05 (5%)
        :param breakout_price_change_score: Breakout的价格变化得分，默认1
        :param breakout_score_threshold: Breakout的得分阈值，默认4
        
        :param channel_r2_high: Channel的R²高分阈值，默认0.65
        :param channel_r2_high_score: Channel的R²高分得分，默认3
        :param channel_r2_medium: Channel的R²中等阈值，默认0.5
        :param channel_r2_medium_score: Channel的R²中等得分，默认2
        :param channel_slope_high: Channel的斜率高分阈值，默认0.001
        :param channel_slope_high_score: Channel的斜率高分得分，默认2
        :param channel_slope_medium: Channel的斜率中等阈值，默认0.0005
        :param channel_slope_medium_score: Channel的斜率中等得分，默认1
        :param channel_adx_high: Channel的ADX高分阈值，默认25
        :param channel_adx_high_score: Channel的ADX高分得分，默认2
        :param channel_adx_medium: Channel的ADX中等阈值，默认18
        :param channel_adx_medium_score: Channel的ADX中等得分，默认1
        :param channel_score_threshold_high: Channel的高分阈值，默认5
        :param channel_score_threshold_low: Channel的低分阈值，默认3
        :param channel_r2_min: Channel的最小R²要求，默认0.4
        
        :param tight_channel_r2_threshold: Tight Channel的R²阈值，默认0.75（R²越高，通道越紧密）
        :param tight_channel_volatility_threshold: Tight Channel的波动率阈值，默认0.02 (2%)（波动率越低，通道越紧密）
        
        :return: 市场模式字符串 ("Breakout", "Tight Channel", "Broad Channel", "Trading Range", "INIT")
        """
        # 数据预处理
        df = df.copy()
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        
        # 移除无效数据
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        
        if len(df) < max(window, min_data_points):
            return "INIT"
        
        # 动态调整实际使用的窗口大小
        actual_window = min(window, len(df) - 1)
        if actual_window < min_window:
            return "INIT"
        
        # --- [1. 价格归一化与斜率分析] ---
        subset = df.iloc[-actual_window:].copy()
        first_price = subset['close'].iloc[0]
        if first_price <= 0:
            return "INIT"
            
        norm_close = (subset['close'].values / first_price) - 1
        
        # 计算线性回归
        y = norm_close.reshape(-1, 1)
        x = np.arange(actual_window).reshape(-1, 1)
        reg = LinearRegression().fit(x, y)
        r2 = reg.score(x, y)
        slope = reg.coef_[0][0]
        
        # 计算价格变化幅度（归一化后的总变化）
        price_change_pct = abs(norm_close[-1])
        
        # 计算波动率（用于区分Tight和Broad Channel）
        # 使用归一化价格的标准差来衡量波动率
        price_volatility = np.std(norm_close)
        # 趋势方向，用斜率符号区分牛/熊
        trend_dir = "Bull" if slope >= 0 else "Bear"
        
        # --- [2. 动态 Z-Score 波动判定（自适应窗口）] ---
        # 计算相对实体比例: (Close-Open)/Open
        body_rel = (df['close'] - df['open']).abs() / (df['open'] + 1e-9)
        
        # 根据实际数据量动态调整滚动窗口
        # 至少需要实际窗口的2倍数据才能计算Z-Score，否则使用全部可用数据
        min_rolling_window = max(actual_window * 2, min_data_points)
        rolling_window = min(min_rolling_window, len(df))
        
        if rolling_window < actual_window * 2:
            # 数据不足时，使用全部数据的统计信息
            rolling_mean = body_rel.mean()
            rolling_std = body_rel.std()
        else:
            rolling_mean = body_rel.rolling(rolling_window, min_periods=actual_window).mean()
            rolling_std = body_rel.rolling(rolling_window, min_periods=actual_window).std()
            rolling_mean = rolling_mean.iloc[-1] if not pd.isna(rolling_mean.iloc[-1]) else body_rel.mean()
            rolling_std = rolling_std.iloc[-1] if not pd.isna(rolling_std.iloc[-1]) else body_rel.std()
        
        # 计算当前Z-Score
        curr_body_rel = body_rel.iloc[-1]
        if rolling_std > 1e-9:
            curr_z = (curr_body_rel - rolling_mean) / rolling_std
        else:
            curr_z = 0
        
        # --- [3. 趋势强度指标] ---
        # ADX需要足够的数据，如果数据不足则使用替代指标
        if len(df) >= window + 1:
            try:
                adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=min(window, len(df) - 1))
                curr_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
            except:
                curr_adx = 0
        else:
            # 数据不足时，使用简单的趋势强度替代
            price_momentum = abs(df['close'].iloc[-1] - df['close'].iloc[0]) / (df['close'].iloc[0] + 1e-9)
            curr_adx = min(price_momentum * 100, 50)  # 粗略映射到ADX范围
        
        # --- [4. 综合评分机制（而非严格阈值）] ---
        # 计算各项得分
        breakout_score = 0
        channel_score = 0
        
        # Breakout评分：考虑Z-Score、ADX、价格变化幅度
        if curr_z > z_threshold:
            breakout_score += breakout_z_high_score
        elif curr_z > z_threshold * breakout_z_medium_ratio:
            breakout_score += breakout_z_medium_score
        
        if curr_adx > breakout_adx_high:
            breakout_score += breakout_adx_high_score
        elif curr_adx > breakout_adx_medium:
            breakout_score += breakout_adx_medium_score
        
        # 价格变化幅度作为补充指标
        if price_change_pct > breakout_price_change_pct:
            breakout_score += breakout_price_change_score
        
        # Channel评分：考虑R²、斜率、ADX
        if r2 > channel_r2_high:
            channel_score += channel_r2_high_score
        elif r2 > channel_r2_medium:
            channel_score += channel_r2_medium_score
        
        # 斜率绝对值越大，趋势越明显
        abs_slope = abs(slope)
        if abs_slope > channel_slope_high:
            channel_score += channel_slope_high_score
        elif abs_slope > channel_slope_medium:
            channel_score += channel_slope_medium_score
        
        if curr_adx > channel_adx_high:
            channel_score += channel_adx_high_score
        elif curr_adx > channel_adx_medium:
            channel_score += channel_adx_medium_score
        
        # --- [5. 模式判定逻辑（优先顺序） ---
        # A. BREAKOUT: 爆发性波动
        if breakout_score >= breakout_score_threshold:
            return "Breakout"
        
        # B. CHANNEL: 明确的趋势通道（细分为Tight和Broad）
        if channel_score >= channel_score_threshold_high:
            # 根据R²和波动率区分Tight和Broad Channel
            if r2 >= tight_channel_r2_threshold and price_volatility <= tight_channel_volatility_threshold:
                return f"Tight Channel ({trend_dir})"
            else:
                return f"Broad Channel ({trend_dir})"
        
        # C. 弱趋势但有一定方向性（降低标准）
        if channel_score >= channel_score_threshold_low and r2 > channel_r2_min:
            # 弱趋势也根据R²和波动率区分
            if r2 >= tight_channel_r2_threshold and price_volatility <= tight_channel_volatility_threshold:
                return f"Tight Channel ({trend_dir})"
            else:
                return f"Broad Channel ({trend_dir})"
        
        # D. 其他情况为震荡区间
        return "Trading Range"



def convert_ohlc_to_numeric(df):
    """将DataFrame中的OHLC列转换为数值类型"""
    ohlc_columns = ['open', 'high', 'low', 'close']
    for col in ohlc_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    return df

if __name__ == '__main__':
    # 使用示例:
    from client import ok_client
    import asyncio

    end_date = "2026-01-12 17:10:01"

    df_5m = asyncio.run(ok_client.get_klines_end_with_specify_time('XAUT-USDT-SWAP', end_date,5, 200, True))
    # df_1h =  asyncio.run(ok_client.get_klines('BTC-USDT-SWAP', 60, 200, False))

    # 将OHLC数据转换为数值类型
    df_5m = convert_ohlc_to_numeric(df_5m)
    # df_1h = convert_ohlc_to_numeric(df_1h)
    print(df_5m.tail())
    
    classifier = UltimateMarketClassifier()
    
    # 使用不同窗口大小和参数进行测试
    state = classifier.get_single_mode(df_5m, window=20, z_threshold=1.5)
    print(f"Window 20: {state}")
    
    state = classifier.get_single_mode(df_5m, window=40, z_threshold=1.5)
    print(f"Window 40: {state}")
    
    state = classifier.get_single_mode(df_5m, window=60, z_threshold=1.5)
    print(f"Window 60: {state}")

    state = classifier.get_single_mode(df_5m, window=80, z_threshold=1.5)
    print(f"Window 80: {state}")
