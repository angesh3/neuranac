"""Bridge Adapters — pluggable connection handlers.

Each adapter handles a specific connection type (NeuraNAC, NeuraNAC-to-NeuraNAC, etc.).
Adapters are auto-discovered and registered with the ConnectionManager on import.
"""
from app.adapters.legacy_nac_adapter import LegacyNacAdapter
from app.adapters.neuranac_to_neuranac_adapter import NeuraNACToNeuraNACAdapter
from app.adapters.generic_rest_adapter import GenericRESTAdapter

__all__ = ["LegacyNacAdapter", "NeuraNACToNeuraNACAdapter", "GenericRESTAdapter"]
