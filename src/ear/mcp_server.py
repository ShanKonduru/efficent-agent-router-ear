"""EAR MCP Server — exposes routing engine as an MCP tool and resource.

Phase 2: implemented after CLI validation is complete.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def serve() -> None:
    """Start the EAR MCP server (stdio transport).

    Implementation deferred to Phase 2 (M4).
    Reuses RouterEngine and RegistryClient from the core layer.
    """
    raise NotImplementedError
