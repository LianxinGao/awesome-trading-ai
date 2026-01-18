from pydantic import BaseModel, Field
from typing import Literal


class AiResponse(BaseModel):
    price_action_summary: str = Field(description="价格行为总结")
    next_kline_observation_target: str = Field(default='', description="下一K线的观察目标")
    direction: Literal['等待', "做多", "做空"] = Field(description="多空方向")
    entry_price: str = Field(default="", description="入场价格")
    take_profit_price: str = Field(default="", description="止盈价格")
    stop_loss_price: str = Field(default="", description="止损价格")


class TradingRangeResponse(BaseModel):
    market_cycle_analysis: str = Field(description="当前区间的上/下界定义及价格行为描述")
    signal_type: str = Field(description="(e.g., Failed Breakout, Second Entry at Edge, Reversal Bar)")
    direction: Literal['等待', "做多", "做空"] = Field(description="多空方向")
    entry_price: str = Field(default="", description="建议入场点（通常是信号K线的高/低点突破入场）")
    take_profit_price: str = Field(default="", description="目标位（通常是区间的另一端或 1:1 盈亏比）")
    stop_loss_price: str = Field(default="", description="止损点（信号K线的另一端外）")
    confidence_score: int = Field(description="1-10分")

class TrendResponse(BaseModel):
    trend_phase: str = Field(description="e.g., Bull Spike, Bear Channel, Early Breakout")
    pullback_assessment: str = Field(description="回调的力度（是多头获利了结还是空头反攻？）")
    direction: Literal['等待', "做多", "做空"] = Field(description="多空方向")
    entry_price: str = Field(default="", description="入场价（回踩 EMA 确认或突破前高/低点入场）")
    take_profit_price: str = Field(default="", description="目标位（基于测量运动 Measured Move 或移动止盈）")
    stop_loss_price: str = Field(default="", description="止损点（置于趋势起始点或最近的波段点）")
    strategy_note: str = Field(default="", description="为什么要在这个位置入场（基于 Brooks 理论说明）,若不进行交易，则为空字符串")
    confidence_score: int = Field(description="1-10分")

class AutoTradeResponse(BaseModel):
    setup_identified: str = Field(description="是否有识别出的价格行为模式")
    reasoning: str = Field(description="理由总结")
    action: Literal['BUY', 'SELL', 'WAIT'] = Field(description="多空方向")
    entry_type: str = Field(description="计划委托/市价委托")
    entry_price: str = Field(default="", description="入场价")
    stop_loss: str = Field(default="", description="止损价")
    take_profit: str = Field(default="", description="止盈价")
    early_close_strategy: str = Field(default="", description="提前平仓策略")

class AutoTradeResponseV2(BaseModel):
    patterns_identified: str = Field(description="列出识别到的形态 ")
    summary: str = Field(description="综合决策理由(在分析中不允许提及具体K线的编号)")
    action: Literal['BUY', 'SELL', 'WAIT'] = Field(description="多空方向")
    entry_type: str = Field(default="", description="计划委托/市价委托")
    entry_price: str = Field(default="", description="入场价")
    stop_loss: str = Field(default="", description="止损价")
    take_profit: str = Field(default="", description="止盈价")
    take_profit_logic: str = Field(default="", description="简述止盈位的计算逻辑")

class MonitoringResponse(BaseModel):
    position_analysis: str = Field(description="持仓分析")
    current_risk_level: str = Field(description="当前风险等级及理由")
    action: Literal['HOLD', 'EXIT'] = Field(description="当前仓位操作")
    reasoning: str = Field(description="先论述背景逻辑，再论述细节理由")

class SaveOrderInfo(BaseModel):
    time: str = Field(description="下一根K线时间")
    action: Literal["BUY", "SELL", "WAIT"] = Field(description="多空方向")
    reason: str = Field(description="理由")
    entry_price: str = Field(description="入场价格")
    stop_loss_price: str = Field(description="止损价格")
    take_profit_price: str = Field(description="止盈价格")