from datetime import datetime, timezone, timedelta
import pytz


def is_us_dst(date=None):
    """
    判断指定日期美国是否处于夏令时（Daylight Saving Time）

    :param date: datetime对象，默认为当前时间
    :return: True表示夏令时，False表示冬令时
    """
    if date is None:
        date = datetime.now()

    # 使用美国东部时区
    eastern = pytz.timezone('US/Eastern')

    # 将日期转换为美国东部时区
    eastern_time = eastern.localize(date) if date.tzinfo is None else date.astimezone(eastern)

    # 检查是否处于夏令时
    return eastern_time.dst() != timedelta(0)


def is_pre_market_time():
    """
    判断当前北京时间是否在美股开盘前半小时（盘前半小时）

    规则：
    - 如果在盘前半小时，返回True
    - 如果不在盘前半小时，返回False
    - 冬令时：美股在北京时间晚上10:30开盘，盘前半小时22:00-22:30返回True
    - 夏令时：美股在北京时间晚上9:30开盘，盘前半小时21:00-21:30返回True

    :return: True表示在盘前半小时，False表示不在盘前半小时
    """
    # 获取当前北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    beijing_time = datetime.now(beijing_tz)

    # 判断美国是否处于夏令时
    is_dst = is_us_dst(beijing_time)

    # 获取当前时间的小时和分钟
    current_hour = beijing_time.hour
    current_minute = beijing_time.minute

    if is_dst:
        # 夏令时：开盘时间是21:30（晚上9:30）
        # 盘前半小时：21:00-21:30 返回True
        if current_hour == 21:
            # 21:00-21:30 在盘前半小时
            return current_minute < 35
        else:
            return False
    else:
        # 冬令时：开盘时间是22:30（晚上10:30）
        # 盘前半小时：22:00-22:30 返回True
        if current_hour == 22:
            # 22:00-22:30 在盘前半小时
            return current_minute < 35
        else:
            return False


if __name__ == '__main__':
    # 测试代码
    beijing_tz = pytz.timezone('Asia/Shanghai')
    beijing_time = datetime.now(beijing_tz)

    is_dst = is_us_dst(beijing_time)
    result = is_pre_market_time()

    print(f"当前北京时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"美国是否处于夏令时: {is_dst}")
    print(f"是否在盘前半小时: {result}")

    if is_dst:
        print("美股开盘时间（北京时间）: 21:30")
        print("盘前半小时: 21:00-21:30")
    else:
        print("美股开盘时间（北京时间）: 22:30")
        print("盘前半小时: 22:00-22:30")
