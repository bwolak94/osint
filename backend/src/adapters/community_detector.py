"""Community Detector — graph community detection for investigation entity graphs.

Identifies clusters of tightly connected entities using modularity optimization.
Two algorithms are provided:

  1. Louvain (default) — greedy modularity maximization.  At each pass every
     node is tentatively moved to the neighbor community that yields the largest
     positive modularity gain.  Passes repeat until no improvement is possible.
     This is a pure-Python single-pass simplification of the full multi-level
     Louvain method; sufficient for the graph sizes typical in OSINT
     investigations (< 10 000 nodes).

  2. Label Propagation — each node adopts the most frequent label among its
     neighbors.  Faster but less stable for small graphs.

Usage::

    detector = CommunityDetector()
    result = await detector.detect(nodes, edges, algorithm="louvain")
    for community in result.communities:
        print(community)   # list of node IDs in this cluster
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CommunityResult:
    """Output of a community detection run.

    Attributes:
        communities:      List of communities; each community is a list of
                          node IDs belonging to that cluster.
        modularity_score: Q score in [-0.5, 1.0].  Higher → stronger
                          community structure.  0 means random graph.
        algorithm_used:   Name of the algorithm that produced this result.
        iteration_count:  Number of optimization passes performed.
        elapsed_ms:       Wall-clock time of the detection run in milliseconds.
    """

    communities: list[list[str]] = field(default_factory=list)
    modularity_score: float = 0.0
    algorithm_used: str = ""
    iteration_count: int = 0
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class CommunityDetector:
    """Detects clusters of tightly connected entities using modularity optimization.

    All heavy computation runs in a thread executor so the event loop is not
    blocked by CPU-bound iteration.
    """

    _SUPPORTED_ALGORITHMS = ("louvain", "label_propagation")

    async def detect(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        algorithm: str = "louvain",
    ) -> CommunityResult:
        """Detect communities in the entity graph.

        Args:
            nodes:     List of node dicts with at minimum an ``id`` key.
                       Optional keys: ``type``, ``value``.
            edges:     List of edge dicts with keys ``from_id``, ``to_id``,
                       and optional ``weight`` (defaults to 1.0).
            algorithm: ``"louvain"`` (default) or ``"label_propagation"``.

        Returns:
            A :class:`CommunityResult` with detected communities and quality
            metrics.  Returns an empty result on any failure rather than
            raising.
        """
        if not nodes:
            log.warning("CommunityDetector.detect called with empty node list")
            return CommunityResult(algorithm_used=algorithm)

        algo = algorithm.lower()
        if algo not in self._SUPPORTED_ALGORITHMS:
            log.warning(
                "Unknown algorithm requested, falling back to louvain",
                requested=algorithm,
            )
            algo = "louvain"

        log.info(
            "Community detection started",
            nodes=len(nodes),
            edges=len(edges),
            algorithm=algo,
        )

        try:
            # Build the adjacency structure once, then delegate CPU work to a
            # thread so the event loop stays free for I/O.
            adjacency = self._build_adjacency(nodes, edges)
            t0 = time.perf_counter()

            loop = asyncio.get_event_loop()
            if algo == "louvain":
                node_to_community, iterations = await loop.run_in_executor(
                    None, self._louvain_with_count, adjacency
                )
            else:
                node_to_community, iterations = await loop.run_in_executor(
                    None, self._label_propagation_with_count, adjacency
                )

            elapsed_ms = (time.perf_counter() - t0) * 1000

            communities = self._group_by_community(node_to_community)
            modularity = self._compute_modularity(adjacency, node_to_community)

            result = CommunityResult(
                communities=communities,
                modularity_score=round(modularity, 4),
                algorithm_used=algo,
                iteration_count=iterations,
                elapsed_ms=round(elapsed_ms, 2),
            )

            log.info(
                "Community detection complete",
                communities=len(communities),
                modularity=result.modularity_score,
                iterations=iterations,
                elapsed_ms=result.elapsed_ms,
            )
            return result

        except Exception as exc:
            log.error("Community detection failed", error=str(exc), exc_info=True)
            return CommunityResult(algorithm_used=algo)

    # ------------------------------------------------------------------
    # Public algorithm entry points (sync, called via executor)
    # ------------------------------------------------------------------

    def _louvain(self, adjacency: dict[str, dict[str, float]]) -> dict[str, int]:
        """Run the Louvain algorithm and return ``node_id → community_id``."""
        node_to_community, _ = self._louvain_with_count(adjacency)
        return node_to_community

    def _label_propagation(self, adjacency: dict[str, dict[str, float]]) -> dict[str, int]:
        """Run label propagation and return ``node_id → community_id``."""
        node_to_community, _ = self._label_propagation_with_count(adjacency)
        return node_to_community

    # ------------------------------------------------------------------
    # Algorithm implementations
    # ------------------------------------------------------------------

    def _louvain_with_count(
        self, adjacency: dict[str, dict[str, float]]
    ) -> tuple[dict[str, int], int]:
        """Greedy modularity maximisation (simplified single-level Louvain).

        Steps:
          1. Assign each node to its own singleton community.
          2. For each node (in random order) compute the modularity gain of
             moving it to each neighbour's community.  Move to the best if
             gain > 0.
          3. Repeat until a full pass produces no improvement.

        Returns:
            (node_to_community, iteration_count)
        """
        if not adjacency:
            return {}, 0

        nodes = list(adjacency.keys())
        # node_id → community_id (ints)
        community: dict[str, int] = {node: idx for idx, node in enumerate(nodes)}

        # Total weight of all edges (sum of all adjacency weights / 2 since
        # we store both directions).
        total_weight = sum(
            weight
            for neighbors in adjacency.values()
            for weight in neighbors.values()
        ) / 2.0

        if total_weight == 0:
            return community, 0

        # Precompute node strengths (sum of edge weights for each node).
        strength: dict[str, float] = {
            node: sum(neighbors.values()) for node, neighbors in adjacency.items()
        }

        iterations = 0
        improved = True
        while improved:
            improved = False
            iterations += 1

            for node in nodes:
                current_comm = community[node]

                # Gather neighbour communities and their total connection weight
                # from *node* to each candidate community.
                comm_weights: dict[int, float] = {}
                for neighbor, weight in adjacency[node].items():
                    c = community[neighbor]
                    comm_weights[c] = comm_weights.get(c, 0.0) + weight

                # Remove node from its current community to assess alternatives.
                # Modularity gain formula (simplified):
                #   ΔQ = [k_i_in - k_i * Σ_tot / (2m)] / m
                # where k_i_in = weight of edges from node to community C,
                #       k_i    = strength of node,
                #       Σ_tot  = sum of all strengths in community C,
                #       m      = total weight.
                node_strength = strength[node]

                # Compute Σ_tot for the current community (excluding the node).
                comm_total: dict[int, float] = {}
                for n, c in community.items():
                    if n != node:
                        comm_total[c] = comm_total.get(c, 0.0) + strength[n]

                best_comm = current_comm
                best_gain = 0.0

                for candidate_comm, k_in in comm_weights.items():
                    if candidate_comm == current_comm:
                        continue
                    sigma_tot = comm_total.get(candidate_comm, 0.0)
                    gain = (k_in - node_strength * sigma_tot / (2.0 * total_weight)) / total_weight
                    if gain > best_gain:
                        best_gain = gain
                        best_comm = candidate_comm

                if best_comm != current_comm:
                    community[node] = best_comm
                    improved = True

        return community, iterations

    def _label_propagation_with_count(
        self, adjacency: dict[str, dict[str, float]]
    ) -> tuple[dict[str, int], int]:
        """Synchronous label propagation community detection.

        Each node adopts the label (community id) most common among its
        neighbours.  Ties are broken by choosing the smallest label.
        Converges when no node changes label in a full pass.

        Returns:
            (node_to_community, iteration_count)
        """
        if not adjacency:
            return {}, 0

        nodes = list(adjacency.keys())
        labels: dict[str, int] = {node: idx for idx, node in enumerate(nodes)}
        iterations = 0
        max_iterations = 100  # guard against cycles

        while iterations < max_iterations:
            iterations += 1
            changed = False

            for node in nodes:
                neighbors = adjacency[node]
                if not neighbors:
                    continue

                # Tally neighbour labels weighted by edge weight.
                tally: dict[int, float] = {}
                for neighbor, weight in neighbors.items():
                    lbl = labels[neighbor]
                    tally[lbl] = tally.get(lbl, 0.0) + weight

                best_label = min(
                    tally, key=lambda l: (-tally[l], l)
                )
                if best_label != labels[node]:
                    labels[node] = best_label
                    changed = True

            if not changed:
                break

        return labels, iterations

    # ------------------------------------------------------------------
    # Graph construction helpers
    # ------------------------------------------------------------------

    def _build_adjacency(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        """Build an undirected weighted adjacency dict from node and edge lists.

        Args:
            nodes: Each node must have an ``id`` key.
            edges: Each edge must have ``from_id`` and ``to_id``; ``weight``
                   defaults to 1.0.

        Returns:
            ``{node_id: {neighbor_id: weight, ...}, ...}``
        """
        adjacency: dict[str, dict[str, float]] = {
            node["id"]: {} for node in nodes if "id" in node
        }

        for edge in edges:
            src = edge.get("from_id", "")
            dst = edge.get("to_id", "")
            weight = float(edge.get("weight", 1.0))

            if not src or not dst:
                continue
            # Ensure both endpoints exist in the adjacency dict even if they
            # were not in the nodes list (defensive).
            adjacency.setdefault(src, {})
            adjacency.setdefault(dst, {})

            # Undirected: store both directions.
            adjacency[src][dst] = adjacency[src].get(dst, 0.0) + weight
            adjacency[dst][src] = adjacency[dst].get(src, 0.0) + weight

        return adjacency

    # ------------------------------------------------------------------
    # Post-processing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_by_community(
        node_to_community: dict[str, int],
    ) -> list[list[str]]:
        """Invert node_to_community map into a list of node-ID lists."""
        groups: dict[int, list[str]] = {}
        for node, comm in node_to_community.items():
            groups.setdefault(comm, []).append(node)
        # Sort for deterministic output; largest communities first.
        return sorted(groups.values(), key=len, reverse=True)

    @staticmethod
    def _compute_modularity(
        adjacency: dict[str, dict[str, float]],
        node_to_community: dict[str, int],
    ) -> float:
        """Compute the Newman-Girvan modularity Q.

        Q = (1/2m) * Σ_{ij} [A_ij - k_i*k_j / 2m] * δ(c_i, c_j)

        Where A_ij is the edge weight, k_i the node strength, m the total
        edge weight, and δ is the Kronecker delta.
        """
        total_weight = sum(
            w for neighbors in adjacency.values() for w in neighbors.values()
        ) / 2.0
        if total_weight == 0:
            return 0.0

        strength: dict[str, float] = {
            n: sum(nbrs.values()) for n, nbrs in adjacency.items()
        }

        q = 0.0
        for node_i, neighbors in adjacency.items():
            for node_j, a_ij in neighbors.items():
                if node_to_community.get(node_i) == node_to_community.get(node_j):
                    expected = strength[node_i] * strength.get(node_j, 0.0) / (2.0 * total_weight)
                    q += a_ij - expected

        return q / (2.0 * total_weight)
