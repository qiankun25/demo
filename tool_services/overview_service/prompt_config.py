from pathlib import Path
from typing import Dict, Optional

from shared.prompt_store import PromptStore

PROMPTS_FILE = Path(__file__).resolve().parent / "prompts.json"

DEFAULT_PROMPTS: Dict[str, Dict[str, str]] = {
    "overview_markdown": {
        "template": "You follow instructions precisely and output markdown only.",
        "description": "System prompt used when calling the SiliconFlow overview model.",
    },
}

_prompt_store = PromptStore(PROMPTS_FILE, DEFAULT_PROMPTS)


def list_prompts() -> Dict[str, Dict[str, str]]:
    return _prompt_store.list_prompts()


def get_prompt_entry(key: str) -> Optional[Dict[str, str]]:
    return _prompt_store.get_prompt(key)


def update_prompt(key: str, template: str, description: Optional[str] = None) -> Dict[str, str]:
    return _prompt_store.update_prompt(key, template=template, description=description)


def render_prompt(key: str, **kwargs: object) -> str:
    entry = _prompt_store.get_prompt(key)
    if not entry:
        raise KeyError(f"prompt {key} is not registered")
    template = entry.get("template", "")
    if not template:
        raise ValueError(f"prompt {key} has an empty template")
    if kwargs:
        try:
            return template.format(**{k: str(v) for k, v in kwargs.items()})
        except KeyError as exc:
            raise ValueError(f"missing placeholder in prompt {key}: {exc}") from exc
    return template

