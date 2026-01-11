import pandas as pd
import numpy as np
import talib
from sklearn.linear_model import LinearRegression

import pandas as pd
import numpy as np
import talib
from sklearn.linear_model import LinearRegression


class UltimateMarketClassifier:
    def __init__(self, window=20, z_threshold=2.0):
        """
        :param window: 计算周期
        :param z_threshold: 偏离度门槛。2.0代表当前波动处于前5%的极端情况（95%置信区间）
        """
        self.window = window
        self.z_threshold = z_threshold

    def get_single_mode(self, df):
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)

        if len(df) < self.window + 20: return "INIT", 0

        # --- [1. 价格归一化与斜率] ---
        subset = df.iloc[-self.window:].copy()
        first_price = subset['close'].iloc[0]
        norm_close = (subset['close'].values / first_price) - 1

        y = norm_close.reshape(-1, 1)
        x = np.arange(self.window).reshape(-1, 1)
        reg = LinearRegression().fit(x, y)
        r2 = reg.score(x, y)
        slope = reg.coef_[0][0]

        # --- [2. 动态 Z-Score 波动判定] ---
        # 计算相对实体比例: (Close-Open)/Open
        body_rel = (df['close'] - df['open']).abs() / df['open']

        # 计算 Z-Score: (当前值 - 均值) / 标准差
        # 这能自动识别当前K线在“该品种”历史上是否属于极端爆发
        rolling_mean = body_rel.rolling(self.window * 5).mean()  # 用更长的周期做基准
        rolling_std = body_rel.rolling(self.window * 5).std()
        z_score = (body_rel - rolling_mean) / (rolling_std + 1e-9)

        curr_z = z_score.iloc[-1]

        # --- [3. 趋势强度] ---
        adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.window)
        curr_adx = adx.iloc[-1]

        # --- [4. 模式判定逻辑] ---
        # A. BREAKOUT (Spike): Z-Score 超过门槛，说明出现了该品种罕见的剧烈波动
        if curr_z > self.z_threshold and curr_adx > 20:
            return "Breakout"

        # B. CHANNEL: 线性度高，且有一定趋势强度
        if r2 > 0.65 and curr_adx > 25:
            return "Channel"

        # C. RANGE: 其他情况
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

# # 使用示例:
# from client import ok_client
# import asyncio
# df_5m = asyncio.run(ok_client.get_klines('BTC-USDT-SWAP', 5, 200, True))
# df_1h =  asyncio.run(ok_client.get_klines('BTC-USDT-SWAP', 60, 200, False))
#
# # 将OHLC数据转换为数值类型
# df_5m = convert_ohlc_to_numeric(df_5m)
# df_1h = convert_ohlc_to_numeric(df_1h)
#
# classifier = UltimateMarketClassifier(window=40, z_threshold=2.0)
# state = classifier.get_market_state(df_5m, df_1h)
# print(state)