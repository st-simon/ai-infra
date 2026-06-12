import os
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "model_policy.yaml"

FALLBACK_POLICY = {
    "default_mode": "local_only",
    "modes": {
        "local_only": {"provider": "local"},
        "low_cost": {"provider": "local"},
        "auto": {"provider": "local"},
        "quality": {"provider": "local"},
    },
    "roles": {
        "fast": {"local": "qwen35-fast"},
        "general": {"local": "qwen35-fast"},
        "generalist": {"local": "qwen35-fast"},
        "reasoner": {"local": "qwen35-fast"},
        "coder": {"local": "qwen2.5-coder:7b"},
        "embedding": {"local": ""},
    },
}


def _load_policy() -> dict:
    if not MODEL_POLICY_PATH.exists():
        return FALLBACK_POLICY
    with open(MODEL_POLICY_PATH, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    policy = dict(FALLBACK_POLICY)
    policy.update(loaded)
    policy["modes"] = {**FALLBACK_POLICY["modes"], **loaded.get("modes", {})}
    policy["roles"] = {**FALLBACK_POLICY["roles"], **loaded.get("roles", {})}
    return policy


def _env_role_name(role: str, provider: str) -> str:
    role_key = role.upper().replace("-", "_")
    provider_key = provider.upper().replace("-", "_")
    return f"MODEL_{role_key}_{provider_key}"


def _select_model(role: str, mode: str | None = None) -> tuple[str, str]:
    policy = _load_policy()
    selected_mode = mode or os.getenv("MODEL_MODE") or policy.get("default_mode", "local_only")
    mode_conf = policy.get("modes", {}).get(selected_mode)
    if not mode_conf:
        raise ValueError(f"Unknown model mode: {selected_mode}")

    provider = mode_conf.get("provider", "local")
    role_conf = policy.get("roles", {}).get(role)
    if not role_conf:
        raise ValueError(f"Unknown model role: {role}")

    model = os.getenv(_env_role_name(role, provider)) or role_conf.get(provider)
    if not model:
        raise ValueError(f"No model configured for role={role} provider={provider}")
    return provider, model


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


def _post_cloud(payload: dict) -> dict:
    raise NotImplementedError(
        "Cloud model provider is allowed by policy but is not wired in this phase."
    )


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
         thinking: bool = False,
         mode: str | None = None) -> str:
    provider, model = _select_model(role, mode)
    content = prompt if thinking else f"/no_think\n{prompt}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    }
    result = _post(payload) if provider == "local" else _post_cloud(payload)
    return _extract(result)

def chat_with_history(role: str, messages: list[dict],
                      temperature: float = 0.7,
                      num_ctx: int = 3072,
                      thinking: bool = False,
                      mode: str | None = None) -> str:
    provider, model = _select_model(role, mode)
    if not thinking and messages:
        msgs = list(messages)
        first = msgs[0].copy()
        if not first["content"].startswith("/no_think"):
            first["content"] = f"/no_think\n{first['content']}"
        msgs[0] = first
    else:
        msgs = messages
    payload = {
        "model": model,
        "messages": msgs,
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    }
    result = _post(payload) if provider == "local" else _post_cloud(payload)
    return _extract(result)
