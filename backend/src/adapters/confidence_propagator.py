"""Confidence Propagator — belief propagation over investigation entity graphs.

Confidence scores (0.0–1.0) assigned to seed entities are propagated through
the graph along weighted edges.  The intuition is:

  - A high-confidence anchor (e.g. a directly observed malicious IP) lends
    partial confidence to entities reachable from it.
  - Each hop degrades the score by a configurable ``decay`` factor.
  - Edge weights modulate how strongly a connection transfers confidence.

Algorithm (iterative max-belief propagation)::

    For each iteration:
        For each node n:
            new_conf[n] = max(
                current_conf[n],
                max(conf[neighbor] * decay * edge_weight[neighbor→n])
                    for neighbor in in_neighbors(n)
            )
    Stop when max|new_conf[n] - conf[n]| < 0.001  or  max_iterations reached.

Because we take the max (not sum) the score never exceeds 1.0 and the
propagation is stable even on cyclic graphs.

Usage::

    propagator = ConfidencePropagator()
    scores = await propagator.propagate(nodes, edges, decay=0.85)
    for node_id, conf in scores.items():
        print(node_id, f"{conf:.3f}")
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

log = structlog.get_logger()

# Convergence threshold — stop when no score changes more than this.
_CONVERGENCE_DELTA = 0.001


class ConfidencePropagator:
    """Propagates confidence scores through an entity relationship graph.

    The propagator is stateless; a new call to :meth:`propagate` is fully
    independent of any previous call.
    """

    async def propagate(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        decay: float = 0.85,
        max_iterations: int = 10,
    ) -> dict[str, float]:
        """Propagate confidence scores from seed nodes through the graph.

        Args:
            nodes:          List of node dicts.  Each must have an ``id`` key
                            and should have a ``confidence`` key (float 0–1).
                            Nodes without ``confidence`` default to 0.0.
            edges:          List of edge dicts with ``from_id``, ``to_id``, and
                            optional ``weight`` (defaults to 1.0).
            decay:          Multiplicative decay applied per hop.  Typical
                            range 0.5–0.95.  Values outside [0, 1] are clamped.
            max_iterations: Hard limit on propagation rounds.

        Returns:
            ``{node_id: propagated_confidence}`` mapping for every node.
            Returns an empty dict on any failure.
        """
        if not nodes:
            log.warning("ConfidencePropagator.propagate called with empty node list")
            return {}

        decay = max(0.0, min(1.0, decay))

        try:
            # Offload the iterative CPU work to a thread executor.
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                self._run_propagation,
                nodes,
                edges,
                decay,
                max_iterations,
            )
            log.info(
                "Confidence propagation complete",
                nodes=len(scores),
                decay=decay,
            )
            return scores
        except Exception as exc:
            log.error("Confidence propagation failed", error=str(exc), exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # Core propagation (sync, runs in thread executor)
    # ------------------------------------------------------------------

    def _run_propagation(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        decay: float,
        max_iterations: int,
    ) -> dict[str, float]:
        """Iterative max-belief propagation — synchronous inner loop."""
        # Initialise confidence from node data.
        scores: dict[str, float] = {}
        for node in nodes:
            node_id = node.get("id", "")
            if not node_id:
                continue
            raw_conf = node.get("confidence", 0.0)
            try:
                scores[node_id] = float(max(0.0, min(1.0, raw_conf)))
            except (TypeError, ValueError):
                scores[node_id] = 0.0

        if not scores:
            return {}

        # Build in-neighbour adjacency:  node_id → list of (src_id, weight)
        in_edges: dict[str, list[tuple[str, float]]] = {n: [] for n in scores}
        for edge in edges:
            src = edge.get("from_id", "")
            dst = edge.get("to_id", "")
            weight = float(edge.get("weight", 1.0))

            # Clamp weight to [0, 1] so it acts as a transmission coefficient.
            weight = max(0.0, min(1.0, weight))

            if src and dst:
                in_edges.setdefault(dst, []).append((src, weight))
                # Treat graph as undirected: propagate in both directions.
                in_edges.setdefault(src, []).append((dst, weight))

        for iteration in range(max_iterations):
            max_delta = 0.0
            new_scores = dict(scores)

            for node_id, in_neighbors in in_edges.items():
                if not in_neighbors:
                    continue

                best_incoming = max(
                    (scores.get(src, 0.0) * decay * weight for src, weight in in_neighbors),
                    default=0.0,
                )
                candidate = max(scores.get(node_id, 0.0), best_incoming)
                candidate = min(candidate, 1.0)

                delta = abs(candidate - scores.get(node_id, 0.0))
                if delta > max_delta:
                    max_delta = delta

                new_scores[node_id] = candidate

            scores = new_scores

            if max_delta < _CONVERGENCE_DELTA:
                log.debug(
                    "Confidence propagation converged",
                    iteration=iteration + 1,
                    max_delta=max_delta,
                )
                break

        return {node_id: round(conf, 4) for node_id, conf in scores.items()}
