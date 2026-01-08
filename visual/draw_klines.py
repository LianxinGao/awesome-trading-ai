import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
from pathlib import Path
# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visual.prepare_draw_data import get_kline_with_ema
import asyncio
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，适用于无GUI环境


def find_local_extrema(data, window_size=11):
    """
    使用滑动窗口检测局部最大值和最小值
    当中间K线的high大于其他所有相邻K线的high时，标记为局部最大值
    当中间K线的low小于其他所有相邻K线的low时，标记为局部最小值
    若右边没有K线了，则左边的K线和最后一根K线比较即可
    """
    local_maxima = []
    local_minima = []
    
    half_window = window_size // 2
    
    for i in range(len(data)):
        # 动态确定窗口范围，确保不超出数据边界
        start_idx = max(0, i - half_window)
        end_idx = min(len(data) - 1, i + half_window)
        
        # 如果是最后一根K线且右边没有K线，则只需要与左边的K线比较
        if i == len(data) - 1 and i + 1 > len(data) - 1:  # 最后一根K线
            # 只要左边有K线，就与左边的K线比较
            if start_idx < i:
                # 检查局部最大值
                current_high = data.iloc[i]['high']
                window_highs = [data.iloc[j]['high'] for j in range(start_idx, i)]
                
                if len(window_highs) > 0 and current_high > max(window_highs):
                    local_maxima.append({
                        'timestamp': data.iloc[i]['timestamp'],
                        'price': current_high,
                        'type': 'max'
                    })
                
                # 检查局部最小值
                current_low = data.iloc[i]['low']
                window_lows = [data.iloc[j]['low'] for j in range(start_idx, i)]
                
                if len(window_lows) > 0 and current_low < min(window_lows):
                    local_minima.append({
                        'timestamp': data.iloc[i]['timestamp'],
                        'price': current_low,
                        'type': 'min'
                    })
        else:
            # 检查局部最大值
            current_high = data.iloc[i]['high']
            window_highs = [data.iloc[j]['high'] for j in range(start_idx, end_idx + 1) if j != i]
            
            if len(window_highs) > 0 and current_high > max(window_highs):
                local_maxima.append({
                    'timestamp': data.iloc[i]['timestamp'],
                    'price': current_high,
                    'type': 'max'
                })
            
            # 检查局部最小值
            current_low = data.iloc[i]['low']
            window_lows = [data.iloc[j]['low'] for j in range(start_idx, end_idx + 1) if j != i]
            
            if len(window_lows) > 0 and current_low < min(window_lows):
                local_minima.append({
                    'timestamp': data.iloc[i]['timestamp'],
                    'price': current_low,
                    'type': 'min'
                })
    
    return local_maxima, local_minima


def plot_candlestick(data, title="Candlestick Chart", figsize=(28, 14), markers=None, entry_price=None, entry_type=None):
    """
    绘制K线图（蜡烛图）
    
    Args:
        data: 包含timestamp, open, high, low, close, ema21列的DataFrame
        title: 图表标题
        figsize: 图表大小
        markers: 标记列表，格式为[{'timestamp': timestamp, 'text': 'text'}, ...]
        entry_price: 成本价，如果不为空，则在图上以水平的虚线标记出成本价
        entry_type: 交易类型，'buy' 或 'sell'，如果不为空，则在成本价标签中显示交易类型
    """
    # 确保数据按时间排序
    data = data.copy()
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data = data.sort_values('timestamp')
    
    # 转换价格列为数值类型
    for col in ['open', 'high', 'low', 'close', 'ema21']:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # 计算价格范围用于调整显示
    all_prices = np.concatenate([data['high'].values, data['low'].values])
    if 'ema21' in data.columns and not data['ema21'].isna().all():
        all_prices = np.concatenate([all_prices, data['ema21'].dropna().values])
    price_range = max(all_prices) - min(all_prices)
    top_buffer = price_range * 0.04  # 价格范围的4%作为顶部缓冲，为标记预留更多空间
    bottom_buffer = price_range * 0.04  # 价格范围的4%作为底部缓冲，为标记预留更多空间
    
    # 计算每个蜡烛图的宽度，基于数据点的平均时间间隔
    if len(data) > 1:
        # 计算时间间隔并增加整体图表宽度，使K线之间自然间隔更大
        time_diff = (mdates.date2num(data.iloc[-1]['timestamp']) - mdates.date2num(data.iloc[0]['timestamp'])) / len(data)
        # 保持K线宽度相对较大，但通过增加图表尺寸来增加间隔
        width = max(time_diff * 0.7, 0.0006)  # 保持相对较大的K线宽度
    else:
        width = 0.0015
    
    # 绘制蜡烛图
    for i in range(len(data)):
        row = data.iloc[i]
        timestamp = mdates.date2num(row['timestamp'])
        open_price = row['open']
        high_price = row['high']
        low_price = row['low']
        close_price = row['close']
        
        # 判断涨跌（收盘价大于开盘价为涨）
        is_up = close_price >= open_price
        color = '#1f77b4' if is_up else '#d62728'  # 蓝色表示上涨，红色表示下跌
        
        # 绘制影线（高低价）- 分成两部分，避开实体
        # 上影线（从实体顶部到最高价）
        top_wick_start = max(open_price, close_price)  # 实体顶部
        if high_price > top_wick_start:
            ax.plot([timestamp, timestamp], [top_wick_start, high_price], 
                    color=color, linewidth=1.2, alpha=0.7, zorder=1)
        
        # 下影线（从实体底部到最低价）
        bottom_wick_end = min(open_price, close_price)  # 实体底部
        if low_price < bottom_wick_end:
            ax.plot([timestamp, timestamp], [low_price, bottom_wick_end], 
                    color=color, linewidth=1.2, alpha=0.7, zorder=1)
        
        # 绘制实体（开盘收盘价）- 作为纯色矩形，没有边框
        # 计算实体的高度和位置
        height = abs(close_price - open_price)
        bottom = min(open_price, close_price)
        
        # 绘制实体矩形，确保在影线之上
        if height > 0:  # 只绘制有高度的实体
            rect = Rectangle((timestamp - width/2, bottom), width, height,
                            facecolor=color, edgecolor='none', linewidth=0, alpha=0.8, zorder=2)
            ax.add_patch(rect)
        else:  # 如果开盘价等于收盘价，绘制一条线
            ax.plot([timestamp - width/2, timestamp + width/2], [open_price, close_price], 
                    color=color, linewidth=2.0, alpha=0.8, zorder=2)
    
    # 绘制EMA21曲线
    if 'ema21' in data.columns and not data['ema21'].isna().all():
        ax.plot(data['timestamp'], data['ema21'], color='#FF6600', linewidth=1.5, label='EMA21', zorder=3)
    
    # 检测并标记局部极值点
    local_maxima, local_minima = find_local_extrema(data, window_size=11)
    
    # 标记局部最大值（在高点上方显示）
    for extrema in local_maxima:
        ax.text(extrema['timestamp'], extrema['price'], f"{extrema['price']:.2f}", 
                fontsize=9, color='green', fontweight='bold', ha='center', va='bottom', zorder=4)
    
    # 标记局部最小值（在低点下方显示）
    for extrema in local_minima:
        ax.text(extrema['timestamp'], extrema['price'], f"{extrema['price']:.2f}", 
                fontsize=9, color='red', fontweight='bold', ha='center', va='top', zorder=4)
    
    # 添加标记
    if markers:
        for marker in markers:
            marker_time = pd.to_datetime(marker['timestamp'])
            marker_text = marker['text']
            # 找到最接近的时间点的价格数据
            closest_row = data.iloc[(data['timestamp'] - marker_time).abs().argsort()[:1]].iloc[0]
            price = max(closest_row['high'], closest_row['ema21']) if 'ema21' in data.columns and not pd.isna(closest_row['ema21']) else closest_row['high']
            
            # 绘制箭头和文本
            ax.annotate(marker_text, 
                       xy=(mdates.date2num(marker_time), price),
                       xytext=(mdates.date2num(marker_time), price * 1.015),  # 稍微高一点的位置
                       arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                       fontsize=12, 
                       color='red',
                       fontweight='bold',
                       ha='center',
                       zorder=4)
    
    # 添加成本价水平虚线
    if entry_price is not None:
        # 根据交易类型设置标签文本
        if entry_type and entry_type.lower() in ['buy', 'sell']:
            label_text = f'Entry Price ({entry_type.upper()} at {entry_price:.2f})'
            # 在虚线上方添加成本价和交易类型标签
            # 获取x轴的范围
            x_min, x_max = ax.get_xlim()
            # 在图表左侧添加成本价标签，包含交易类型
            ax.text(x_min, entry_price, f'  {entry_type.upper()} at {entry_price:.2f}', 
                    fontsize=10, color='purple', fontweight='bold', ha='left', va='bottom', zorder=5)
        else:
            label_text = f'Entry Price: {entry_price:.2f}'
            # 获取x轴的范围
            x_min, x_max = ax.get_xlim()
            # 在图表左侧添加成本价标签
            ax.text(x_min, entry_price, f'  {entry_price:.2f}', 
                    fontsize=10, color='purple', fontweight='bold', ha='left', va='bottom', zorder=5)
        
        # 绘制水平虚线表示成本价
        ax.axhline(y=entry_price, color='purple', linestyle='--', linewidth=1.5, alpha=0.8, label=label_text, zorder=3)
    
    # 设置x轴格式
    # 根据数据量调整x轴标签密度
    if len(data) <= 50:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))  # 每12小时一个主刻度
    elif len(data) <= 100:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=24))  # 每24小时一个主刻度
    else:  # 适用于200根K线的情况
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))  # 每天一个主刻度
    
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 设置标签和标题
    ax.set_xlabel('Time', fontsize=14)
    ax.set_ylabel('Price', fontsize=14)
    ax.set_title(title, fontsize=20, fontweight='bold')
    
    # 设置y轴范围，增加一些空间让图表更美观，为标记预留空间
    ax.set_ylim(min(all_prices) - bottom_buffer, max(all_prices) + top_buffer)
    
    # 为最后10根K线添加数字标记（0-9），统一排列在图表最下方
    num_last_klines = min(10, len(data))
    last_klines_data = data.tail(num_last_klines)
    for idx, (i, row) in enumerate(last_klines_data.iterrows()):
        timestamp = mdates.date2num(row['timestamp'])
        # 将数字标记统一排列在图表底部
        ax.text(timestamp, min(all_prices) - bottom_buffer * 0.7, str(idx), 
                fontsize=10, color='purple', fontweight='bold', ha='center', va='top', zorder=5)
    
    # 添加网格
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # 添加图例（如果EMA21存在或成本价标记）
    legend_elements = []
    if 'ema21' in data.columns and not data['ema21'].isna().all():
        legend_elements.append(plt.Line2D([0], [0], color='#FF6600', linewidth=1.5, label='EMA21'))
    if entry_price is not None:
        if entry_type and entry_type.lower() in ['buy', 'sell']:
            legend_elements.append(plt.Line2D([0], [0], color='purple', linestyle='--', linewidth=1.5, label=f'Entry Price ({entry_type.upper()} at {entry_price:.2f})'))
        else:
            legend_elements.append(plt.Line2D([0], [0], color='purple', linestyle='--', linewidth=1.5, label=f'Entry Price: {entry_price:.2f}'))
    
    if legend_elements:
        ax.legend(handles=legend_elements, loc='upper left')
    
    # 自动调整布局
    plt.tight_layout()
    
    return fig, ax


if __name__ == "__main__":
    # 获取数据
    data = asyncio.run(get_kline_with_ema("BTC-USDT-SWAP", 15, 200, 2, False))
    print("Data shape:", data.shape)
    print(data.tail())
    
    # 示例标记数据
    markers = [
        {'timestamp': '2026-1-08 10:45:00', 'text': 'entry place'},
    ]
    
    # 绘制K线图并保存 - 显示全部数据（最多200根）
    fig, ax = plot_candlestick(data, title="15-min Candlestick Chart", markers=markers, entry_price=90980, entry_type='BUY')
    # plt.show()
    # 保存到根目录下的 data 文件夹
    root_dir = Path(__file__).parent.parent  # 获取项目根目录
    output_path = root_dir / "data" / "kline_chart.png"
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    print(f"Candlestick chart saved as {output_path}")
    plt.close()  # 关闭图形以释放内存
