from __future__ import annotations

import re
import unicodedata


SENSITIVE_REPLY = "您的问题包含敏感内容，请调整表述。"

SYSTEM_ACTION_TERMS = (
    "打开",
    "启动",
    "运行",
    "执行",
    "调用",
    "新建",
    "创建",
    "写入",
    "写一个",
    "读取",
    "修改",
    "删除",
    "复制",
    "移动",
    "重命名",
    "下载",
    "安装",
    "卸载",
    "清理",
    "格式化",
)

LOCAL_RESOURCE_TERMS = (
    "我的电脑",
    "此电脑",
    "资源管理器",
    "文件管理器",
    "文件",
    "文件夹",
    "目录",
    "路径",
    "桌面",
    "下载目录",
    "注册表",
    "系统设置",
    "控制面板",
    "任务管理器",
    "浏览器",
    "应用",
    "软件",
)

COMMAND_TERMS = (
    "cmd",
    "powershell",
    "shell",
    "终端",
    "命令行",
    "命令提示符",
    "bat",
    "脚本",
    "脚本文件",
)

SENSITIVE_EXACT_PHRASES = (
    "打开我的电脑",
    "打开此电脑",
    "打开资源管理器",
    "在d盘写一个文件",
    "在c盘写一个文件",
    "运行命令",
    "执行命令",
    "删除文件",
    "读取文件",
    "修改文件",
)

DRIVE_PATH_PATTERN = re.compile(r"\b[a-z]:[\\/]")
DRIVE_MENTION_PATTERN = re.compile(r"\b[a-z]\s*盘\b")


def is_sensitive_request(content: str) -> bool:
    query = normalize_sensitive_text(content)
    if not query:
        return False
    if any(phrase in query for phrase in SENSITIVE_EXACT_PHRASES):
        return True
    if DRIVE_PATH_PATTERN.search(query) or DRIVE_MENTION_PATTERN.search(query):
        return any(term in query for term in SYSTEM_ACTION_TERMS + LOCAL_RESOURCE_TERMS)
    if any(term in query for term in COMMAND_TERMS):
        return any(term in query for term in SYSTEM_ACTION_TERMS)
    return any(term in query for term in SYSTEM_ACTION_TERMS) and any(
        term in query for term in LOCAL_RESOURCE_TERMS
    )


def normalize_sensitive_text(content: str) -> str:
    value = unicodedata.normalize("NFKC", content).lower()
    value = value.replace("，", " ").replace("。", " ").replace("？", " ").replace("！", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()
