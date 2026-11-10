import math
import random

import networkx as nx
import pytest

from app.modules.routing.graph import NoPath, all_pairs, astar, dijkstra, haversine_heuristic, knn_graph

# a small graph with a known shortest path: A-B-D (cost 3) beats A-C-D (cost 5) and A-D (cost 10)
G = {
    "A": {"B": 1, "C": 2, "D": 10},
    "B": {"A": 1, "D": 2},
    "C": {"A": 2, "D": 3},
    "D": {"A": 10, "B": 2, "C": 3},
    "Z": {},
}


def test_dijkstra_known_graph():
    r = dijkstra(G, "A", "D")
    assert r.path == ["A", "B", "D"] and r.cost == 3 and r.expanded >= 3
    assert dijkstra(G, "A", "A").path == ["A"] and dijkstra(G, "A", "A").cost == 0


def test_unreachable_and_invalid_weights():
    with pytest.raises(NoPath):
        dijkstra(G, "A", "Z")
    with pytest.raises(NoPath):
        astar(G, "A", "Z", lambda a, b: 0)
    with pytest.raises(ValueError):
        dijkstra({"A": {"B": -1}, "B": {}}, "A", "B")
    with pytest.raises(ValueError):
        dijkstra({"A": {"B": float("nan")}, "B": {}}, "A", "B")


def test_astar_with_zero_heuristic_equals_dijkstra():
    assert astar(G, "A", "D", lambda a, b: 0).path == dijkstra(G, "A", "D").path


def random_geometric(seed, n=40, k=4):
    rng = random.Random(seed)
    coords = {i: (26.8 + rng.random() * 0.4, 75.6 + rng.random() * 0.4) for i in range(n)}
    return coords, knn_graph(coords, k)


@pytest.mark.parametrize("seed", range(8))
def test_dijkstra_and_astar_match_networkx_on_random_graphs(seed):
    coords, g = random_geometric(seed)
    nxg = nx.Graph()
    for u, nb in g.items():
        for v, w in nb.items():
            nxg.add_edge(u, v, weight=w)
    h = haversine_heuristic(
        coords, scale=1.0
    )  # weights are great-circle x 1.3 >= great-circle: admissible and consistent
    rng = random.Random(seed + 100)
    for _ in range(15):
        a, b = rng.sample(sorted(coords), 2)
        if not nx.has_path(nxg, a, b):
            with pytest.raises(NoPath):
                dijkstra(g, a, b)
            continue
        expected = nx.dijkstra_path_length(nxg, a, b)
        d, s = dijkstra(g, a, b), astar(g, a, b, h)
        assert d.cost == pytest.approx(expected) and s.cost == pytest.approx(expected)
        assert nx.astar_path_length(nxg, a, b, heuristic=h) == pytest.approx(expected)
        # the returned path really has that cost
        assert sum(g[x][y] for x, y in zip(s.path, s.path[1:], strict=False)) == pytest.approx(expected)


def test_astar_expands_no_more_nodes_than_dijkstra_in_aggregate():
    total_d = total_a = 0
    for seed in range(8):
        coords, g = random_geometric(seed, n=60, k=5)
        h = haversine_heuristic(coords)
        rng = random.Random(seed)
        for _ in range(10):
            a, b = rng.sample(sorted(coords), 2)
            try:
                total_d += dijkstra(g, a, b).expanded
                total_a += astar(g, a, b, h).expanded
            except NoPath:
                pass
    assert 0 < total_a <= total_d  # a good admissible heuristic never needs more expansions overall


def test_inadmissible_heuristic_can_lose_optimality_so_it_is_documented():
    # heuristic overestimates the true remaining cost of the cheap route through B
    bad = {"A": 0, "B": 100, "C": 0, "D": 0}.get
    r = astar(G, "A", "D", lambda n, t: bad(n, 0))
    assert r.cost >= dijkstra(G, "A", "D").cost  # never better than optimal, sometimes worse


def test_all_pairs_and_knn_graph_properties():
    coords, g = random_geometric(1, n=12, k=3)
    assert all(g[a][b] == g[b][a] for a in g for b in g[a])  # symmetric
    assert all(len(nb) >= 3 for nb in g.values())  # each node has at least its k nearest
    ap = all_pairs(g, list(coords)[:5])
    assert ap[(0, 0)] == 0 and all(not math.isnan(v) for v in ap.values())
    sub = list(coords)[:5]
    assert all(ap[(a, b)] == pytest.approx(ap[(b, a)]) for a in sub for b in sub)
