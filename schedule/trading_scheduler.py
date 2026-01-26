import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Callable, List
from client import ok_client
from client.ok_models import TdMode


class TradingScheduler:
    """交易调度器，负责定时执行交易决策"""
    
    def __init__(self, agent_func: Callable, time_interval: int = 15):
        """
        初始化调度器
        
        Args:
            agent_func: 要执行的交易代理函数
        """
        self.agent_func = agent_func
        self.running = False
        self.time_interval = time_interval

        # result = ok_client.set_leverage(config.TRADING_INST_ID, config.LEVERAGE, TdMode.CROSS)
        # print(f"设置合约杠杆为{config.LEVERAGE}倍: {result}")
        # print("交易调度器已初始化")
    
    def get_next_run_time(self) -> datetime:
        now = datetime.now()
        
        # 计算当前x分钟周期的开始时间
        current_cycle_start = now.replace(
            minute=(now.minute // self.time_interval) * self.time_interval,
            second=0,
            microsecond=0
        )
        
        # 下次运行时间 = 当前周期开始时间 + x分
        next_run = current_cycle_start + timedelta(minutes=self.time_interval, seconds=5)
        
        # 如果已经过了这个时间，则计算下一个x分钟周期
        if next_run <= now:
            next_run += timedelta(minutes=self.time_interval)
        
        return next_run
    
    async def run_once(self):
        """执行一次交易决策"""
        try:
            print("开始执行交易决策...")
            result = await self.agent_func()
            return result
        except Exception as e:
            traceback.print_exc()
            print(f"执行交易决策时发生错误: {e}")
            return None
        finally:
            # 每次执行后清理内存，防止长期运行导致内存泄漏
            import gc
            gc.collect()
    
    async def start(self):
        """启动调度器"""
        self.running = True
        print("交易调度器已启动")
        
        while self.running:
            try:
                # 计算下次运行时间
                next_run_time = self.get_next_run_time()
                wait_seconds = (next_run_time - datetime.now()).total_seconds()
                
                print(f"下次执行时间: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"等待时间: {wait_seconds:.1f}秒")
                
                # 等待到执行时间
                await asyncio.sleep(wait_seconds)
                
                if self.running:
                    await self.run_once()
                    
            except Exception as e:
                print(f"调度器运行时发生错误: {e}")
                traceback.print_exc()
                await asyncio.sleep(60)  # 出错后等待1分钟再继续
    
    async def start_with_immediate_execution(self):
        """启动调度器并立即执行一次"""
        # 立即执行一次
        print("立即执行交易决策...")
        await self.run_once()
        
        # 然后按计划执行
        await self.start()
    
    def stop(self):
        """停止调度器"""
        self.running = False
        print("交易调度器已停止")