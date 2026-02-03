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


def is_market_open_time():
    """
    判断当前北京时间是否处于美股开盘的前半小时和后半小时内
    
    规则：
    - 冬令时：美股在北京时间晚上10:30开盘，所以10:00-11:00返回True
    - 夏令时：美股在北京时间晚上9:30开盘，所以9:00-10:00返回True
    
    :return: True表示在开盘前后半小时内，False表示不在
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
        # 前半小时：21:00-21:30
        # 后半小时：21:30-22:00
        # 总共：21:00-22:00（不包括22:00）
        return current_hour == 21
    else:
        # 冬令时：开盘时间是22:30（晚上10:30）
        # 前半小时：22:00-22:30
        # 后半小时：22:30-23:00
        # 总共：22:00-23:00（不包括23:00）
        return current_hour == 22


if __name__ == '__main__':
    # 测试代码
    beijing_tz = pytz.timezone('Asia/Shanghai')
    beijing_time = datetime.now(beijing_tz)
    
    is_dst = is_us_dst(beijing_time)
    result = is_market_open_time()
    
    print(f"当前北京时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"美国是否处于夏令时: {is_dst}")
    print(f"是否在开盘前后半小时内: {result}")
    
    if is_dst:
        print("美股开盘时间（北京时间）: 21:30")
        print("有效时间段: 21:00-22:00")
    else:
        print("美股开盘时间（北京时间）: 22:30")
        print("有效时间段: 22:00-23:00")
