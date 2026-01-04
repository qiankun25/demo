import json
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


class PromptStore:
    """
    Simple JSON-backed prompt registry.
    """

    def __init__(self, path: Path, defaults: Dict[str, Dict[str, str]]):
        self._path = path
        self._lock = Lock()
        self._defaults = {
            key: {"template": value.get("template", ""), "description": value.get("description", "")}
            for key, value in defaults.items()
        }
        self._prompts: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        persisted: Dict[str, Dict[str, str]] = {}
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, entry in raw.items():
                        if not isinstance(entry, dict):
                            continue
                        persisted[key] = {
                            "template": str(entry.get("template") or "").strip(),
                            "description": str(entry.get("description") or "").strip(),
                        }
            except Exception:  # pragma: no cover - best effort load
                persisted = {}

        merged = {}
        merged.update(persisted)
        for key, default in self._defaults.items():
            if key not in merged or not merged[key].get("template"):
                merged[key] = {
                    "template": default["template"],
                    "description": default.get("description", ""),
                }
            elif not merged[key].get("description") and default.get("description"):
                merged[key]["description"] = default["description"]

        self._prompts = merged
        self._persist()

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._path.write_text(json.dumps(self._prompts, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_prompts(self) -> Dict[str, Dict[str, str]]:
        with self._lock:
            return {key: value.copy() for key, value in self._prompts.items()}

    def get_prompt(self, key: str) -> Optional[Dict[str, str]]:
        with self._lock:
            entry = self._prompts.get(key)
            return entry.copy() if entry else None

    def update_prompt(self, key: str, template: str, description: Optional[str] = None) -> Dict[str, str]:
        if not template or not isinstance(template, str):
            raise ValueError("template must be a non-empty string")
        with self._lock:
            entry = self._prompts.get(key, {"template": "", "description": ""})
            entry["template"] = template.strip()
            if description is not None:
                entry["description"] = description.strip()
            self._prompts[key] = entry
            self._persist()
            return entry.copy()

