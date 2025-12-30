from schedule.trading_scheduler import TradingScheduler
from workflow.run_workflow import run_workflow
import asyncio
from client import ok_client
from client.ok_models import TdMode
from coin_configs import coin_configs


for config in coin_configs:
    inst_id = config['inst_id']
    result = ok_client.set_leverage(inst_id, "100", TdMode.CROSS)
    print(f"设置{inst_id}的合约杠杆为100倍")

trading_scheduler = TradingScheduler(agent_func=run_workflow)
asyncio.run(trading_scheduler.start_with_immediate_execution())