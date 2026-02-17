from __future__ import annotations

from darwincode.agents.claude_code import ClaudeCodeVendor
from darwincode.agents.vendor import AgentVendor

_VENDORS: dict[str, type[AgentVendor]] = {
    "claude-code": ClaudeCodeVendor,
}


def get_vendor(name: str) -> AgentVendor:
    """Look up an agent vendor by name."""
    vendor_cls = _VENDORS.get(name)
    if vendor_cls is None:
        available = ", ".join(_VENDORS.keys())
        raise ValueError(f"Unknown agent vendor '{name}'. Available: {available}")
    return vendor_cls()


def register_vendor(name: str, vendor_cls: type[AgentVendor]) -> None:
    """Register a new agent vendor."""
    _VENDORS[name] = vendor_cls
