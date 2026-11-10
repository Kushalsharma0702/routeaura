"""Shortest-path algorithms on explicit weighted graphs (pure Python, no I/O).

`dijkstra` and `astar` are our own implementations, tested for parity against NetworkX. They operate on
an adjacency mapping {node: {neighbour: weight}} with non-negative weights.

Important: this is *graph* routing. It is only as good as the graph you give it. A TSP-style visiting
order (see optimizer.py) is a different problem, and neither is real road-network routing: actual road
distances and times must come from a configured routing provider.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass

from app.modules.spatial.geo import haversine_m

Node = Hashable
Graph = Mapping[Node, Mapping[Node, float]]


@dataclass(frozen=True)
class PathResult:
    path: list[Node]
    cost: float
    expanded: int  # nodes popped from the frontier: a measure of search effort


class NoPath(Exception):
    pass


def _validate(g: Graph) -> None:
    for u, nbrs in g.items():
        for v, w in nbrs.items():
            if w < 0 or math.isnan(w):
                raise ValueError(f"edge {u!r}->{v!r} has an invalid weight {w}")


def dijkstra(g: Graph, source: Node, target: Node) -> PathResult:
    """Dijkstra with a binary heap. Raises NoPath when the target is unreachable."""
    _validate(g)
    dist: dict[Node, float] = {source: 0.0}
    prev: dict[Node, Node] = {}
    heap: list[tuple[float, int, Node]] = [(0.0, 0, source)]
    counter, expanded, done = 1, 0, set()
    while heap:
        d, _, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        expanded += 1
        if u == target:
            return PathResult(_unwind(prev, source, target), d, expanded)
        for v, w in g.get(u, {}).items():
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, counter, v))
                counter += 1
    raise NoPath(f"no path from {source!r} to {target!r}")


def astar(g: Graph, source: Node, target: Node, heuristic: Callable[[Node, Node], float]) -> PathResult:
    """A*. `heuristic(n, target)` must be admissible (never overestimate) and, for optimality with a closed
    set, consistent. With an admissible and consistent heuristic the result equals Dijkstra's."""
    _validate(g)
    g_score: dict[Node, float] = {source: 0.0}
    prev: dict[Node, Node] = {}
    heap: list[tuple[float, int, Node]] = [(heuristic(source, target), 0, source)]
    counter, expanded, closed = 1, 0, set()
    while heap:
        _, _, u = heapq.heappop(heap)
        if u in closed:
            continue
        closed.add(u)
        expanded += 1
        if u == target:
            return PathResult(_unwind(prev, source, target), g_score[u], expanded)
        for v, w in g.get(u, {}).items():
            ng = g_score[u] + w
            if ng < g_score.get(v, math.inf):
                g_score[v], prev[v] = ng, u
                heapq.heappush(heap, (ng + heuristic(v, target), counter, v))
                counter += 1
    raise NoPath(f"no path from {source!r} to {target!r}")


def _unwind(prev: dict[Node, Node], source: Node, target: Node) -> list[Node]:
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    return path[::-1]


def haversine_heuristic(
    coords: Mapping[Node, tuple[float, float]], scale: float = 1.0
) -> Callable[[Node, Node], float]:
    """Great-circle distance x `scale`. Admissible when every edge weight >= scale * great-circle distance of
    its endpoints (e.g. weights are road metres and scale <= 1)."""

    def h(a: Node, b: Node) -> float:
        (la, lo), (lb, lob) = coords[a], coords[b]
        return haversine_m(la, lo, lb, lob) * scale

    return h


def knn_graph(coords: Mapping[Node, tuple[float, float]], k: int, detour: float = 1.3) -> dict[Node, dict[Node, float]]:
    """Symmetric k-nearest-neighbour graph over points, weights = great-circle metres x detour.
    A *synthetic* graph for tests/benchmarks and the offline estimate: it is NOT a road network."""
    nodes = list(coords)
    g: dict[Node, dict[Node, float]] = {n: {} for n in nodes}
    for a in nodes:
        near = sorted((n for n in nodes if n != a), key=lambda n: (haversine_m(*coords[a], *coords[n]), str(n)))[:k]
        for b in near:
            w = haversine_m(*coords[a], *coords[b]) * detour
            g[a][b] = g[b][a] = w
    return g


def all_pairs(g: Graph, nodes: list[Node]) -> dict[tuple[Node, Node], float]:
    """Shortest-path costs between every ordered pair of `nodes` (inf if unreachable)."""
    out: dict[tuple[Node, Node], float] = {}
    for a in nodes:
        for b in nodes:
            if a == b:
                out[(a, b)] = 0.0
                continue
            try:
                out[(a, b)] = dijkstra(g, a, b).cost
            except NoPath:
                out[(a, b)] = math.inf
    return out
