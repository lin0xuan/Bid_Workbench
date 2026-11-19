# 这个脚本负责管理前端模型名称和真实大模型接口名称的对应关系。
# -*- coding: utf-8 -*-
import os
from typing import Dict


LLM_VENDOR_OPTIONS: Dict[str, str] = {
    "deepseek": "DeepSeek",
    "siliconflow": "硅基流动",
}


LLM_VENDOR_BASE_URLS: Dict[str, str] = {
    "deepseek": "https://api.deepseek.com",
    "siliconflow": "https://api.siliconflow.cn/v1",
}


SILICONFLOW_MODEL_OPTIONS: Dict[str, str] = {
    "DeepSeek-V4-Pro": "deepseek-ai/DeepSeek-V4-Pro",
    "Kimi-K2.6 (Pro)": "Pro/moonshotai/Kimi-K2.6",
    "GLM-5.1 (Pro)": "Pro/zai-org/GLM-5.1",
    "MiniMax-M2.5": "MiniMaxAI/MiniMax-M2.5",
    "GLM-4.7 (Pro)": "Pro/zai-org/GLM-4.7",
    "DeepSeek-R1 (Pro)": "deepseek-ai/DeepSeek-R1",
    "Qwen3.6-35B-A3B": "Qwen/Qwen3.6-35B-A3B",
    "Qwen3-8B (轻量)": "Qwen/Qwen3-8B",
    "GLM-4-9B-Chat (轻量)": "THUDM/glm-4-9b-chat",
    "DeepSeek-R1-Distill-Qwen-7B (轻量)": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "Kimi-K2-Instruct (轻量)": "moonshotai/Kimi-K2-Instruct",
}


DEEPSEEK_MODEL_OPTIONS: Dict[str, str] = {
    # 官方接口 ID。deepseek-flash 当前对应 DeepSeek-V4.1-Flash。
    "DeepSeek V4.1 Flash": "deepseek-flash",
}


_VENDOR_MODELS: Dict[str, Dict[str, str]] = {
    "deepseek": DEEPSEEK_MODEL_OPTIONS,
    "siliconflow": SILICONFLOW_MODEL_OPTIONS,
}


def resolve_llm_model(vendor: str, model_name: str) -> str:
    """Resolve UI model display name to provider API model id."""
    options = _VENDOR_MODELS.get(vendor)
    if options is None:
        supported = ", ".join(LLM_VENDOR_OPTIONS)
        raise ValueError(f"Unsupported LLM vendor: {vendor}. Supported: {supported}")

    if model_name in options:
        return options[model_name]

    if model_name in options.values():
        return model_name

    supported = ", ".join(options)
    raise ValueError(f"Unsupported {vendor} model: {model_name}. Supported: {supported}")


def resolve_llm_base_url(vendor: str) -> str:
    """Resolve provider API base URL."""
    if vendor not in LLM_VENDOR_BASE_URLS:
        supported = ", ".join(LLM_VENDOR_BASE_URLS)
        raise ValueError(f"Unsupported LLM vendor: {vendor}. Supported: {supported}")
    return LLM_VENDOR_BASE_URLS[vendor]


def resolve_llm_selection(
    vendor: str,
    model_name: str,
) -> tuple[str, str]:
    """Resolve per-request configuration without changing process environment."""
    resolved_model = resolve_llm_model(vendor, model_name)
    base_url = resolve_llm_base_url(vendor)

    return resolved_model, base_url
