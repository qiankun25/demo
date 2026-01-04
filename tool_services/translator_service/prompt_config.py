from pathlib import Path
from typing import Dict, Optional

from shared.prompt_store import PromptStore

PROMPTS_FILE = Path(__file__).resolve().parent / "prompts.json"

DEFAULT_PROMPTS: Dict[str, Dict[str, str]] = {
    "multimodal_translation": {
        "template": (
            "You are a professional multilingual translator.\n"
            "You will be given text and optionally images.\n"
            "Task:\n"
            "1) Translate the given text into {target_lang}.\n"
            "2) For each image, produce a caption in {target_lang}. If there is readable text, extract it and translate it into {target_lang}.\n"
            "Return STRICT JSON with this schema:\n"
            '{{"text_translated": string, "images_translated": [{{"input": string, "caption": string, "extracted_text": string, "translated_text": string}}]}}'
        ),
        "description": "Used when translating text+image payloads via SiliconFlow multimodal chat.",
    },
    "image_caption": {
        "template": "You are a helpful assistant. Describe the image in {target_lang}. Return a short caption only.",
        "description": "Used by the translator fallback path that only captions images.",
    },
    "text_translation": {
        "template": (
            "You are a professional multilingual translator.\n"
            "Please translate the following text from {source_lang} to {target_lang}.\n"
            "Return ONLY the translated text."
        ),
        "description": "Used by the unified backend text translation fallback (SiliconFlow text chat).",
    },
}

_prompt_store = PromptStore(PROMPTS_FILE, DEFAULT_PROMPTS)


def list_prompts() -> Dict[str, Dict[str, str]]:
    """Return a copy of registered prompts."""
    return _prompt_store.list_prompts()


def get_prompt_entry(key: str) -> Optional[Dict[str, str]]:
    """Fetch metadata for a single prompt key."""
    return _prompt_store.get_prompt(key)


def update_prompt(key: str, template: str, description: Optional[str] = None) -> Dict[str, str]:
    """Overwrite a prompt template and optional description."""
    return _prompt_store.update_prompt(key, template=template, description=description)


def render_prompt(key: str, **kwargs: object) -> str:
    """Render the prompt template with the provided keyword arguments."""
    entry = _prompt_store.get_prompt(key)
    if not entry:
        raise KeyError(f"prompt {key} is not registered")
    template = entry.get("template", "")
    if not template:
        raise ValueError(f"prompt {key} has an empty template")
    try:
        return template.format(**{k: str(v) for k, v in kwargs.items()})
    except KeyError as exc:
        raise ValueError(f"missing placeholder in prompt {key}: {exc}") from exc

