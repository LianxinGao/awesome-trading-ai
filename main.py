from schedule.trading_scheduler import TradingScheduler
from workflow.run_workflow import run_workflow
import asyncio


def run_single_inst():
    # 运行所有币种的配置
    return asyncio.run(run_workflow())


trading_scheduler = TradingScheduler(agent_func=run_single_inst)
trading_scheduler.start_with_immediate_execution()