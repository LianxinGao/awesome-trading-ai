from schedule.trading_scheduler import TradingScheduler
from workflow.run_workflow import run_workflow
import asyncio


trading_scheduler = TradingScheduler(agent_func=run_workflow, time_interval=5)
asyncio.run(trading_scheduler.start_with_immediate_execution())