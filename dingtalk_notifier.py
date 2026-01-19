import os
import time
import hmac
import hashlib
import base64
import logging
from typing import Optional
from dotenv import load_dotenv

import requests

# 加载环境变量
load_dotenv()
logger = logging.getLogger(__name__)


def _build_signed_webhook(base_url: str, secret: Optional[str]) -> str:
    """
    如果配置了 DINGTALK_SECRET，则根据钉钉安全设置生成带 timestamp 与 sign 的完整 webhook URL。
    如果未配置 secret，则直接返回原始 webhook。
    """
    if not secret:
        return base_url

    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")

    # 按钉钉要求进行 URL 编码
    from urllib.parse import quote_plus

    return f"{base_url}&timestamp={timestamp}&sign={quote_plus(sign)}"


def send_dingtalk_text(content: str) -> bool:
    """
    发送纯文本消息到钉钉群机器人。

    环境变量:
        DINGTALK_WEBHOOK: 机器人完整 webhook 地址（必填）
        DINGTALK_SECRET:  机器人安全设置的加签 secret（可选）
        DINGTALK_KEYWORD: 消息必须包含的关键字（可选，若配置则自动前缀）
    """
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")
    keyword = os.getenv("DINGTALK_KEYWORD")

    if not webhook:
        logger.error("DINGTALK_WEBHOOK 未配置，无法发送钉钉消息")
        return False

    # 确保符合安全设置：自动加上关键字前缀
    final_content = f"{keyword} {content}" if keyword else content

    url = _build_signed_webhook(webhook, secret)

    payload = {
        "msgtype": "text",
        "text": {
            "content": final_content
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            logger.error("钉钉消息发送失败，HTTP %s, 响应: %s", resp.status_code, resp.text)
            return False

        data = {}
        try:
            data = resp.json()
        except Exception:
            # 有些情况下钉钉返回非 JSON，但基本都会是 JSON，这里兼容一下
            logger.warning("钉钉响应非 JSON，原始响应: %s", resp.text)

        # 钉钉通常使用 errcode == 0 表示成功
        if isinstance(data, dict) and data.get("errcode", 0) != 0:
            logger.error("钉钉返回错误: errcode=%s, errmsg=%s", data.get("errcode"), data.get("errmsg"))
            return False

        logger.info("钉钉消息发送成功: %s", final_content)
        return True
    except Exception as e:
        logger.error("发送钉钉消息异常: %s", e)
        return False


if __name__ == "__main__":
    """
    简单命令行测试入口:
        在已正确配置 .env / 环境变量后执行:
            python dingtalk_notifier.py
        按提示输入要发送的测试内容。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    test_content = input("请输入要发送到钉钉群的测试消息内容（回车发送）: ").strip()
    if not test_content:
        print("内容为空，已取消发送。")
    else:
        ok = send_dingtalk_text(test_content)
        print("发送结果:", "成功" if ok else "失败")

