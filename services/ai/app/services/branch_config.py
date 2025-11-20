"""
Branch configuration helper for setting up branch-specific contexts
"""
from typing import Dict, Any
from app.services.conversation_manager import conversation_manager


# Branch configurations for all 9 branches
BRANCH_CONFIGS: Dict[str, Dict[str, Any]] = {
    "kano": {
        "name": "KSCHMA Kano Branch",
        "abbreviation": "KSCHMA",
        "modes": ["standard", "premium"],
        "location": "Kano, Nigeria",
        "region": "North West"
    },
    "kogi": {
        "name": "KGSHIA Kogi Branch",
        "abbreviation": "KGSHIA",
        "modes": ["standard", "premium"],
        "location": "Kogi, Nigeria",
        "region": "North Central"
    },
    "kaduna": {
        "name": "KADCHMA Kaduna Branch",
        "abbreviation": "KADCHMA",
        "modes": ["standard", "premium"],
        "location": "Kaduna, Nigeria",
        "region": "North West"
    },
    "fct": {
        "name": "FHIS FCT Branch",
        "abbreviation": "FHIS",
        "modes": ["standard", "premium"],
        "location": "Federal Capital Territory, Nigeria",
        "region": "North Central"
    },
    "adamawa": {
        "name": "ASCHMA Adamawa Branch",
        "abbreviation": "ASCHMA",
        "modes": ["standard", "premium"],
        "location": "Adamawa, Nigeria",
        "region": "North East"
    },
    "zamfara": {
        "name": "ZAMCHEMA Zamfara Branch",
        "abbreviation": "ZAMCHEMA",
        "modes": ["standard", "premium"],
        "location": "Zamfara, Nigeria",
        "region": "North West"
    },
    "sokoto": {
        "name": "SOHEMA Sokoto Branch",
        "abbreviation": "SOHEMA",
        "modes": ["standard", "premium"],
        "location": "Sokoto, Nigeria",
        "region": "North West"
    },
    "rivers": {
        "name": "RIVCHPP Rivers Branch",
        "abbreviation": "RIVCHPP",
        "modes": ["standard", "premium"],
        "location": "Rivers, Nigeria",
        "region": "South South"
    },
    "osun": {
        "name": "OSHIA Osun Branch",
        "abbreviation": "OSHIA",
        "modes": ["standard", "premium"],
        "location": "Osun, Nigeria",
        "region": "South West"
    }
}


def initialize_branches():
    """Initialize all branch contexts"""
    for branch_id, config in BRANCH_CONFIGS.items():
        conversation_manager.set_branch_context(branch_id, config)
    print(f"✅ Initialized {len(BRANCH_CONFIGS)} branch configurations")


def get_branch_info(branch_id: str) -> Dict[str, Any]:
    """Get branch information"""
    return conversation_manager.get_branch_context(branch_id)

