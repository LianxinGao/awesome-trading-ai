from schedule.trading_scheduler import TradingScheduler
from workflow.run_workflow_v2 import run_workflow
import asyncio
from coin_configs import target_coins
from client import ok_client
from client.ok_models import TdMode


res = ok_client.set_position_mode('long_short_mode')
print(f'设置用户模式：{res}')

for coin_config in target_coins:
    inst_id = coin_config['inst_id']
    leverage = coin_config['leverage']
    ok_client.set_leverage(inst_id, leverage, TdMode.CROSS, 'long')
    ok_client.set_leverage(inst_id, leverage, TdMode.CROSS, 'short')
    print(f"设置{inst_id}的合约杠杆为{leverage}倍")

trading_scheduler = TradingScheduler(agent_func=run_workflow, time_interval=15, target_minute=14, target_second=40)
asyncio.run(trading_scheduler.start())