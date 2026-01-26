import json
import asyncio
import traceback
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

T = TypeVar('T', bound=BaseModel)

async def request_ai(
    system_prompt: str, 
    user_prompt: str, 
    image_bytes_list: list[bytes], 
    response_model: Type[T],
    max_retries: int = 3,
    timeout: int = 120
) -> Optional[Dict[Any, Any]]:
    """
    调用 Gemini API 进行 AI 分析
    
    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        image_bytes_list: 图像字节列表
        response_model: 响应模型类型
        max_retries: 最大重试次数，默认3次
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        解析后的响应字典，如果失败返回 None
    """
    last_exception = None
    
    for attempt in range(max_retries):
        client = None
        try:
            # 准备图像数据
            image_datas = [types.Part.from_bytes(data=image_bytes, mime_type='image/png') 
                          for image_bytes in image_bytes_list]
            contents = image_datas + [user_prompt]
            
            # 优化：创建客户端后立即使用，使用完后清理图像数据
            client = genai.Client()
            
            # 使用 asyncio.wait_for 设置超时
            async def _call_api():
                # 注意：genai.Client().models.generate_content 是同步调用
                # 需要在线程中执行以避免阻塞事件循环
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-3-flash-preview",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            response_json_schema=response_model.model_json_schema(),
                            temperature=0.7
                        )
                    )
                )
                return response
            
            # 执行 API 调用，带超时
            response = await asyncio.wait_for(_call_api(), timeout=timeout)
            
            # 解析响应
            if not response or not hasattr(response, 'text') or not response.text:
                raise ValueError("API 返回空响应")
            
            recipe = response_model.model_validate_json(response.text)
            result_dict = recipe.model_dump()
            
            if attempt > 0:
                print(f"AI API 调用成功（第 {attempt + 1} 次尝试）")
            
            # 优化：使用完后立即清理图像数据
            del image_datas, contents
            import gc
            gc.collect()
            
            return result_dict
            
        except asyncio.TimeoutError:
            last_exception = Exception(f"API 调用超时（超过 {timeout} 秒）")
            print(f"AI API 调用超时，第 {attempt + 1}/{max_retries} 次尝试")
            # 优化：清理资源
            if 'image_datas' in locals():
                del image_datas
            if 'contents' in locals():
                del contents
            import gc
            gc.collect()
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避：2秒、4秒、8秒
            continue
            
        except ValidationError as e:
            last_exception = e
            print(f"AI API 响应解析失败（第 {attempt + 1} 次尝试）: {e}")
            # 验证错误通常不会因为重试而解决，直接返回 None
            traceback.print_exc()
            # 优化：清理资源
            if 'image_datas' in locals():
                del image_datas
            if 'contents' in locals():
                del contents
            import gc
            gc.collect()
            return None
            
        except Exception as e:
            last_exception = e
            error_msg = str(e)
            print(f"AI API 调用失败（第 {attempt + 1}/{max_retries} 次尝试）: {error_msg}")
            traceback.print_exc()
            
            # 优化：清理资源
            if 'image_datas' in locals():
                del image_datas
            if 'contents' in locals():
                del contents
            import gc
            gc.collect()
            
            # 如果是认证错误或配额错误，不重试
            if "quota" in error_msg.lower() or "quota" in error_msg.lower():
                print("检测到配额限制，停止重试")
                return None
            if "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                print("检测到认证错误，停止重试")
                return None
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                print(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                print(f"AI API 调用失败，已达到最大重试次数 {max_retries}")
    
    # 所有重试都失败
    if last_exception:
        print(f"AI API 调用最终失败: {last_exception}")
    return None

async def request_ai_direct(
    system_prompt: str, 
    prompt: str, 
    image_bytes_list: list[bytes],
    max_retries: int = 3,
    timeout: int = 120
) -> Optional[str]:
    """
    直接调用 Gemini API，返回原始文本响应
    
    Args:
        system_prompt: 系统提示词
        prompt: 用户提示词
        image_bytes_list: 图像字节列表
        max_retries: 最大重试次数，默认3次
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        API 返回的文本，如果失败返回 None
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            image_datas = [types.Part.from_bytes(data=image_bytes, mime_type='image/png') 
                          for image_bytes in image_bytes_list]
            contents = image_datas + [prompt]
            
            client = genai.Client()
            
            # 使用 asyncio.wait_for 设置超时
            async def _call_api():
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-3-flash-preview",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            temperature=0.7,
                        )
                    )
                )
                return response
            
            response = await asyncio.wait_for(_call_api(), timeout=timeout)
            
            if not response or not hasattr(response, 'text'):
                raise ValueError("API 返回空响应")
            
            if attempt > 0:
                print(f"AI API 调用成功（第 {attempt + 1} 次尝试）")
            
            return response.text
            
        except asyncio.TimeoutError:
            last_exception = Exception(f"API 调用超时（超过 {timeout} 秒）")
            print(f"AI API 调用超时，第 {attempt + 1}/{max_retries} 次尝试")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            continue
            
        except Exception as e:
            last_exception = e
            error_msg = str(e)
            print(f"AI API 调用失败（第 {attempt + 1}/{max_retries} 次尝试）: {error_msg}")
            traceback.print_exc()
            
            if "quota" in error_msg.lower() or "authentication" in error_msg.lower():
                print("检测到配额或认证错误，停止重试")
                return None
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                print(f"AI API 调用失败，已达到最大重试次数 {max_retries}")
    
    if last_exception:
        print(f"AI API 调用最终失败: {last_exception}")
    return None