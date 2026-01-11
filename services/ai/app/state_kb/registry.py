"""
KB registry for the state/provider RAG system.

The "sources" are filesystem folders containing FAQs/policies for that KB.
This repo already has state folders under `app/rag/faqs/branches/{state_id}` and provider
docs under `app/rag/faqs/providers/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KBDef:
    kb_id: str
    display_name: str
    sources: tuple[Path, ...]


def get_kbs() -> dict[str, KBDef]:
    base = Path(__file__).resolve().parent.parent  # .../app

    # Existing doc sources in this repo
    state_base = base / "rag" / "faqs" / "branches"
    providers_base = base / "rag" / "faqs" / "providers"

    kbs = {
        "adamawa": KBDef("adamawa", "Adamawa State", (state_base / "adamawa",)),
        "fct": KBDef("fct", "FCT / Abuja", (state_base / "fct",)),
        "kano": KBDef("kano", "Kano State", (state_base / "kano",)),
        "zamfara": KBDef("zamfara", "Zamfara State", (state_base / "zamfara",)),
        "kogi": KBDef("kogi", "Kogi State", (state_base / "kogi",)),
        "osun": KBDef("osun", "Osun State", (state_base / "osun",)),
        "rivers": KBDef("rivers", "Rivers State", (state_base / "rivers",)),
        "sokoto": KBDef("sokoto", "Sokoto State", (state_base / "sokoto",)),
        "kaduna": KBDef("kaduna", "Kaduna State", (state_base / "kaduna",)),
        "providers": KBDef("providers", "Providers", (providers_base,)),
    }
    return kbs


def require_kb(kb_id: str) -> KBDef:
    kb_id = (kb_id or "").strip().lower()
    kbs = get_kbs()
    if kb_id not in kbs:
        raise KeyError(f"Unknown kb_id: {kb_id}")
    return kbs[kb_id]


