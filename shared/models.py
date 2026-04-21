import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MODEL_MAP = {
    "reasoner":   os.getenv("MODEL_REASONER",   "qwen35-fast"),
    "generalist": os.getenv("MODEL_GENERALIST",  "qwen35-fast"),
    "coder":      os.getenv("MODEL_CODER",       "qwen2.5-coder:7b"),
}


def _clean(raw: str) -> str:
    """清理模型输出，过滤掉 thinking 残留"""
    # 去掉 </think> 之前的内容
    if "</think>" in raw:
        raw = raw.split("</think>")[-1]
    # 过滤掉以 * 开头的行（thinking 泄漏）
    lines = raw.strip().splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*") or stripped.startswith("-   "):
            continue
        if "Let's" in stripped or "Count:" in stripped:
            continue
        clean_lines.append(stripped)
    result = " ".join(clean_lines).strip()
    return result

def _post(payload: dict) -> dict:
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=180.0,
        trust_env=False
    )
    response.raise_for_status()
    return response.json()


def _extract(result: dict) -> str:
    """从 API 响应提取文字，content 为空时从 thinking 里取"""
    msg = result.get("message", {})
    content = msg.get("content", "").strip()
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    if content:
        return content
    # content 为空时，从 thinking 里提取最后一段
    thinking = msg.get("thinking", "")
    if thinking:
        lines = [l.strip() for l in thinking.strip().splitlines() if l.strip()]
        # 取 thinking 最后几行（通常是最终结论）
        return lines[-1] if lines else ""
    return ""

def chat(role: str, prompt: str,
         temperature: float = 0.7,
         num_ctx: int = 3072,
         thinking: bool = False) -> str:
    content = prompt if thinking else f"/no_think\n{prompt}"
    result = _post({
        "model": MODEL_MAP[role],
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    })
    return _extract(result)

def chat_with_history(role: str, messages: list[dict],
                      temperature: float = 0.7,
                      num_ctx: int = 3072,
                      thinking: bool = False) -> str:
    if not thinking and messages:
        msgs = list(messages)
        first = msgs[0].copy()
        if not first["content"].startswith("/no_think"):
            first["content"] = f"/no_think\n{first['content']}"
        msgs[0] = first
    else:
        msgs = messages
    result = _post({
        "model": MODEL_MAP[role],
        "messages": msgs,
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    })
    return _extract(result)
