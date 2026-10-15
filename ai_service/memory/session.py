from typing import Dict, Any

# Simple in-memory session store (In production, use Redis)
_session_store: Dict[str, Dict[str, Any]] = {}

def get_session_state(session_id: str) -> Dict[str, Any]:
    """Retrieve the ephemeral session state."""
    if session_id not in _session_store:
        _session_store[session_id] = {}
    return _session_store[session_id]

def update_session_state(session_id: str, updates: Dict[str, Any]):
    """Update the ephemeral session state."""
    state = get_session_state(session_id)
    state.update(updates)

def clear_session_state(session_id: str):
    """Clear session state."""
    if session_id in _session_store:
        del _session_store[session_id]
