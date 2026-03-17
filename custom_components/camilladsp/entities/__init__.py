"""CamillaDSP entity subpackage.

Exports the descriptor framework and builder for external consumption.
"""

from .builder import build_descriptors, diff_descriptors
from .descriptors import EntityDescriptor, EntityPlatform, MutationStrategy
from .utils import sanitize_id

__all__ = [
    "EntityDescriptor",
    "EntityPlatform",
    "MutationStrategy",
    "build_descriptors",
    "diff_descriptors",
    "sanitize_id",
]
