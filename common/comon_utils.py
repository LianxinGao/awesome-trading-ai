from datetime import datetime, timedelta
import subprocess
from pathlib import Path

from ai.models import SaveOrderInfo
from common.store import ObjectStore
import os

from typing import TypeVar, Type, Optional

T = TypeVar('T')

project_root = Path(__file__).parent.parent
data_path = f"{project_root}/data"
store = ObjectStore(data_path)


def move_time_backward(date_string, interval_minutes, N):
    # 将字符串转换为整数
    timestamp_ms = int(date_string)

    # 转换为秒级时间戳并生成 datetime 对象
    date_object = datetime.fromtimestamp(timestamp_ms / 1000)

    # 格式化为可读的日期字符串
    formatted_date = date_object.strftime('%Y-%m-%d %H:%M:%S')

    print(f"当前系统时间：{formatted_date}，获取前 {N} 个 {interval_minutes}分钟 周期的数据")
    # 计算新的时间
    new_date_object = date_object - timedelta(minutes=interval_minutes * N)
    new_date_object = new_date_object.replace(microsecond=0, second=0)

    # 转换为 Unix 时间戳（秒级），然后乘以 1000 得到毫秒级时间戳
    timestamp_ms = int(new_date_object.timestamp() * 1000)

    return timestamp_ms


def get_timestamp(date):
    return int(datetime.strptime(date, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

def get_date(timestamp):
    return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")

def play_system_sound(os_name):
    if os_name == "mac":
        subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=True)


def save_ticket(inst_id: str, ticket_data: str):
    # date_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    # store.save(f"{inst_id}_{date_time}", ticket_data, "tickets")
    store.save(f"{inst_id}", ticket_data, "tickets")

def save_analysis(inst_id: str, ticket_data: str):
    date_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    store.save(f"{inst_id}_{date_time}", ticket_data, "analysis")

def load_latest_ticket(inst_id, cls: Type[T])-> Optional[T]:
    try:
        # file_name = list(sorted(os.listdir(f"{data_path}/tickets")))[-1]
        return store.load_obj(inst_id, cls,"tickets")
    except Exception as e:
        print(e)
        return None


def load_latest_analysis(cls: Type[T])-> Optional[T]:
    try:
        file_name = list(sorted(os.listdir(f"{data_path}/analysis")))[-1]
        ticket = store.load_obj(file_name.split('.')[0], cls,"analysis")
        return ticket
    except Exception as e:
        print(e)
        return None

if __name__ == '__main__':
    ticket = load_latest_ticket('BTC-USDT-SWAP', SaveOrderInfo)
    print(ticket)