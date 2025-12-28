import httpx
import settings
import logging
logger = logging.Logger(__name__)


tg_api_url = f"https://api.telegram.org/bot"

async def tg_bot_http_post(message_text):
    api_url = f"{tg_api_url}{settings.tg_bot_token}/sendMessage"

    # 构建请求体
    request_data = {
        "chat_id": settings.tg_chat_id,
        "text": message_text,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(timeout=10000) as client:
            if request_data:
                response = await client.post(api_url, data=request_data, follow_redirects=True)
            else:
                response = await client.post(api_url, data=request_data, follow_redirects=True)

            # 检查响应状态码
            if response.status_code == 200:
                # 如果响应内容是JSON格式，可以使用 response.json() 来获取
                return response.json()
            elif response.status_code == 429:
                logger.info(f"HTTP request fail，code：{response.status_code},请求频率过快")
                return "None"
            else:
                logger.info(f"HTTP request fail，code：{response.status_code},response:{response.text}")
                return "None"

    except Exception as e:
        logger.error(f"HTTP request fail，error:{e}")
        return "None"

if __name__ == '__main__':
    import asyncio
    asyncio.run(tg_bot_http_post("ojbk, Mr Zhou!"))