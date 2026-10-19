"""Policy implementations for Hearth context optimization (BUILD_HANDBOOK §5).

Re-exports relocation, offloading, compaction, and routing policies.
"""

from hearth.compaction import (
    CompactionPlan,
    compute_compaction_payback,
)
from hearth.layout import optimize_layout
from hearth.offload import (
    BlobStore,
    get_blob_store,
    is_read_tool_registered,
    offload_large_tool_outputs,
)
from hearth.policies.route import (
    RouteDecision,
    RouteVerdict,
    calculate_break_even_n,
    evaluate_route,
)

__all__ = [
    "optimize_layout",
    "BlobStore",
    "get_blob_store",
    "is_read_tool_registered",
    "offload_large_tool_outputs",
    "CompactionPlan",
    "compute_compaction_payback",
    "RouteVerdict",
    "RouteDecision",
    "calculate_break_even_n",
    "evaluate_route",
]
