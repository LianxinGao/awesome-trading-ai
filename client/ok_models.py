from pydantic import BaseModel, Field
from typing import List
from typing import Literal, Optional
from decimal import Decimal
from enum import Enum

class OrderType(Enum):
    LIMIT = "limit" # 限价单
    OPTIMAL_LIMIT_LOC = "optimal_limit_ioc" # 市价单


class TdMode(Enum):
    CROSS = "cross" # 全仓
    ISOLATED = "isolated" # 逐仓


class Ticket(BaseModel):
    # pos_id: str # 持仓ID
    inst_id: str # 产品ID
    pos_side: str # 持仓方向
    avg_px: str # 开仓均价
    liq_px: str # 强平价格
    upl: str # 浮动盈亏(USDT)
    upl_ratio: str # 浮动收益率
    be_px: str # 盈亏平衡价
    lever: str # 杠杆倍数
    create_time: str # 创建时间

class CompletedTicket(BaseModel):
    inst_id: str = Field(description="产品ID")
    direction: str = Field(description="持仓方向")
    open_avg_px: str = Field(description="开仓均价")
    close_avg_px: str = Field(description="平仓均价")
    pnl: float = Field(description="盈亏")
    fee: float = Field(description="手续费")
    realized_pnl: float = Field(description="实盈亏")
    completed_time: str = Field(description="完成时间")