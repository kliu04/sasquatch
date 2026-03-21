from __future__ import annotations

import math
from dataclasses import dataclass, field

from api.schemas import Hold

# ---------------------------------------------------------------------------
# Constants — all distance thresholds in metres (real-world units from PLY)
# ---------------------------------------------------------------------------

DIFFICULTY_BUDGETS: dict[str, float] = {
    "easy":   8.0,
    "medium": 5.0,
    "hard":   3.0,
}

STYLE_PARAMS: dict[str, dict] = {
    "static":  {"mn": 0.15, "mx": 0.80, "alpha": 1.5, "max_downward_frac": 0.10},
    "dynamic": {"mn": 0.30, "mx": 1.50, "alpha": 0.5, "max_downward_frac": 0.15},
}

_EPSILON = 1e-6

# ---------------------------------------------------------------------------
# Internal node — wraps a Hold with computed difficulty and pixel position
# ---------------------------------------------------------------------------

@dataclass
class _Node:
    hold_id: int
    # 3D world position (metres) — used for distance / sparsify
    x3d: float
    y3d: float
    z3d: float
    # Pixel y — used for top/bottom zone classification
    px_y: float
    depth: float
    area: int
    difficulty: float = 0.0


@dataclass
class _Graph:
    nodes: dict[int, _Node] = field(default_factory=dict)
    # adj: hold_id -> [(neighbor_id, cost)]  (directed, asymmetric)
    adj: dict[int, list[tuple[int, float]]] = field(default_factory=dict)

    def add_node(self, node: _Node) -> None:
        self.nodes[node.hold_id] = node
        self.adj.setdefault(node.hold_id, [])

    def add_directed_edge(self, a: int, b: int, cost: float) -> None:
        self.adj[a].append((b, cost))

    def remove_edges_between(self, a: int, b: int) -> None:
        self.adj[a] = [(n, c) for n, c in self.adj[a] if n != b]
        self.adj[b] = [(n, c) for n, c in self.adj[b] if n != a]

    def edge_count(self) -> int:
        return sum(len(v) for v in self.adj.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dist3d(a: _Node, b: _Node) -> float:
    return math.sqrt((a.x3d - b.x3d) ** 2 + (a.y3d - b.y3d) ** 2 + (a.z3d - b.z3d) ** 2)


def _assign_difficulty(nodes: list[_Node]) -> None:
    """Normalise difficulty [0, 1] across all nodes in-place.

    Difficulty = inverse of (depth × area):
      - flush holds (small depth) → harder
      - small holds (small area) → harder
    """
    raw = [1.0 / ((n.depth + _EPSILON) * (n.area + _EPSILON)) for n in nodes]
    lo, hi = min(raw), max(raw)
    span = hi - lo if hi > lo else 1.0
    for node, r in zip(nodes, raw):
        node.difficulty = (r - lo) / span


def _edge_cost(a: _Node, b: _Node, dist: float, alpha: float) -> float:
    """Cost of the move a → b: distance + penalty for landing on a hard hold."""
    return dist + alpha * b.difficulty


# ---------------------------------------------------------------------------
# Graph passes
# ---------------------------------------------------------------------------

def _build_graph(holds: list[Hold], alpha: float) -> _Graph:
    g = _Graph()
    for hold in holds:
        px_cx = (hold.bbox.x1 + hold.bbox.x2) / 2
        px_cy = (hold.bbox.y1 + hold.bbox.y2) / 2
        g.add_node(_Node(
            hold_id=hold.id,
            x3d=hold.position.x,
            y3d=hold.position.y,
            z3d=hold.position.z,
            px_y=px_cy,
            depth=hold.depth,
            area=int(hold.confidence * 10_000),  # proxy: use confidence-scaled area
        ))

    nodes = list(g.nodes.values())
    _assign_difficulty(nodes)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            dist = _dist3d(a, b)
            g.add_directed_edge(a.hold_id, b.hold_id, _edge_cost(a, b, dist, alpha))
            g.add_directed_edge(b.hold_id, a.hold_id, _edge_cost(b, a, dist, alpha))

    return g


def _sparsify(graph: _Graph, mn: float, mx: float) -> None:
    """Remove directed edges whose raw 3D distance is outside [mn, mx] metres."""
    to_remove: list[tuple[int, int]] = []
    for a_id, neighbors in graph.adj.items():
        a = graph.nodes[a_id]
        for b_id, _ in neighbors:
            dist = _dist3d(a, graph.nodes[b_id])
            if dist < mn or dist > mx:
                to_remove.append((a_id, b_id))

    for a_id, b_id in to_remove:
        graph.adj[a_id] = [(n, c) for n, c in graph.adj[a_id] if n != b_id]


def _search_routes(
    graph: _Graph,
    budget: float,
    style: str,
    top_k: int,
    zone_fraction: float = 0.15,
) -> list[list[int]]:
    """Budget-constrained DFS from bottom holds to top holds.

    Uses pixel y for zone classification (image top = low y = wall top).
    Allows upward, lateral, and small downward moves.
    """
    ys = [n.px_y for n in graph.nodes.values()]
    y_min, y_max = min(ys), max(ys)
    y_range = y_max - y_min

    zone_thresh = y_range * zone_fraction
    bottom_ids = {nid for nid, n in graph.nodes.items() if n.px_y >= y_max - zone_thresh}
    top_ids    = {nid for nid, n in graph.nodes.items() if n.px_y <= y_min + zone_thresh}

    max_downward_px = y_range * STYLE_PARAMS[style]["max_downward_frac"]

    results: list[tuple[float, list[int]]] = []

    def dfs(cur_id: int, remaining: float, path: list[int], visited: set[int]) -> None:
        if cur_id in top_ids:
            results.append((remaining, list(path)))
            return
        cur_py = graph.nodes[cur_id].px_y
        for nb_id, cost in graph.adj[cur_id]:
            if nb_id in visited:
                continue
            if graph.nodes[nb_id].px_y > cur_py + max_downward_px:
                continue
            if remaining - cost < 0:
                continue
            visited.add(nb_id)
            path.append(nb_id)
            dfs(nb_id, remaining - cost, path, visited)
            path.pop()
            visited.remove(nb_id)

    for start_id in bottom_ids:
        dfs(start_id, budget, [start_id], {start_id})

    results.sort(key=lambda p: p[0])
    return [path for _, path in results[:top_k]]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_routes(
    holds: list[Hold],
    difficulty: str = "medium",
    style: str = "static",
    wingspan: float = 1.8,
    top_k: int = 20,
    gemini_k: int = 3,
) -> list[list[int]]:
    """Build climbing routes from a list of detected holds.

    Args:
        holds:      Hold objects with 3D positions and depth from scan_service
        difficulty: "easy" | "medium" | "hard" — sets budget in metres
        style:      "static" | "dynamic" — sets move distance range and alpha
        wingspan:   max reachable distance in metres (caps sparsify mx)
        top_k:      max DFS candidates before Gemini filter
        gemini_k:   final routes returned
    """
    if difficulty not in DIFFICULTY_BUDGETS:
        raise ValueError(f"difficulty must be one of {list(DIFFICULTY_BUDGETS)}")
    if style not in STYLE_PARAMS:
        raise ValueError(f"style must be one of {list(STYLE_PARAMS)}")

    params = STYLE_PARAMS[style]
    budget = DIFFICULTY_BUDGETS[difficulty]
    mn = params["mn"]
    mx = min(params["mx"], wingspan)
    alpha: float = params["alpha"]

    g = _build_graph(holds, alpha=alpha)
    _sparsify(g, mn, mx)
    candidates = _search_routes(g, budget, style=style, top_k=top_k)

    # Pass 4: Gemini filter stub
    return candidates[:gemini_k]
