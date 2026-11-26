"""The test range: fake tool servers that hold canary secrets.

Nothing here touches the real network or the real disk. Everything that leaves is
recorded, so whether a secret got out is a fact the eval can check, not a guess.
"""

from trustlayer.testrange.canaries import CANARIES
from trustlayer.testrange.world import Outbound, ToolSpec, World, build_world

__all__ = ["CANARIES", "Outbound", "ToolSpec", "World", "build_world"]
