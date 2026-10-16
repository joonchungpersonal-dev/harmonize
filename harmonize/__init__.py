"""harmonize — deterministic data harmonization engine with an optional LLM shell.

The engine (this package) runs standalone from a frozen crosswalk config and
calls no LLM. An LLM is used only, optionally, to *propose* a crosswalk from
codebooks; once frozen, runs are zero-token and byte-identical.
"""

from .engine import ENGINE_VERSION, apply, profile
from .schema import Crosswalk

__all__ = ["apply", "profile", "Crosswalk", "ENGINE_VERSION"]
