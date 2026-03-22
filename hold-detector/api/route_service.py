from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from api.schemas import Hold

# ---------------------------------------------------------------------------
# Constants — all distance thresholds in metres (real-world units from PLY)
# ---------------------------------------------------------------------------

DIFFICULTY_BUDGETS: dict[str, float] = {
    "easy":   10.0,
    "medium": 6.0,
    "hard":   4.0,
}

STYLE_PARAMS: dict[str, dict] = {
    "static":  {"mn": 0.10, "mx": 1.20, "alpha": 1.5, "max_downward_frac": 0.10},
    "dynamic": {"mn": 0.30, "mx": 1.80, "alpha": 0.5, "max_downward_frac": 0.20},
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
    # Pixel position — used for zone classification and visualization
    px_x: float
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

    Combines two independently-normalised signals:
      - depth (60%): flush holds (small depth) → harder
      - area  (40%): small holds (small area) → harder
    Depth is weighted more because it better reflects how grabbable a hold is.
    """
    depth_scores = [1.0 / (n.depth + _EPSILON) for n in nodes]
    area_scores = [1.0 / (n.area + _EPSILON) for n in nodes]

    def _norm(vals: list[float]) -> list[float]:
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi > lo else 1.0
        return [(v - lo) / span for v in vals]

    d_norm = _norm(depth_scores)
    a_norm = _norm(area_scores)

    for node, d, a in zip(nodes, d_norm, a_norm):
        node.difficulty = 0.6 * d + 0.4 * a


def _edge_cost(a: _Node, b: _Node, dist: float, alpha: float) -> float:
    """Cost of the move a → b: distance + penalty for landing on a hard hold."""
    return dist + alpha * b.difficulty


# Target average hold difficulty for each difficulty level (0=easiest, 1=hardest)
_DIFFICULTY_TARGETS: dict[str, float] = {"easy": 0.25, "medium": 0.50, "hard": 0.75}


def _score_route(
    path: list[int],
    graph: _Graph,
    style: str,
    difficulty: str,
) -> float:
    """Score a route higher = better. Considers coverage, style fit, difficulty match."""
    if len(path) < 2:
        return 0.0

    nodes = [graph.nodes[hid] for hid in path]

    # 1. Coverage: more holds = better (uses more of the wall)
    coverage = len(path) / max(len(graph.nodes), 1)

    # 2. Style fit: static prefers short moves, dynamic prefers long moves
    move_dists = [_dist3d(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)]
    avg_dist = sum(move_dists) / len(move_dists)
    params = STYLE_PARAMS[style]
    ideal_dist = params["mn"] if style == "static" else params["mx"]
    style_fit = 1.0 / (1.0 + abs(avg_dist - ideal_dist))

    # 3. Difficulty match: route avg difficulty should match the target
    avg_diff = sum(n.difficulty for n in nodes) / len(nodes)
    target = _DIFFICULTY_TARGETS.get(difficulty, 0.5)
    diff_fit = 1.0 / (1.0 + abs(avg_diff - target))

    return coverage * 0.3 + style_fit * 0.4 + diff_fit * 0.3


def _dedupe_routes(routes: list[list[int]], max_overlap: float = 0.60, max_per_start: int = 3) -> list[list[int]]:
    """Remove routes that share >max_overlap holds. Limit routes per starting hold."""
    kept: list[list[int]] = []
    used_starts: dict[int, int] = {}  # start_id -> count
    for route in routes:
        start_id = route[0]
        if used_starts.get(start_id, 0) >= max_per_start:
            continue
        route_set = set(route)
        duplicate = False
        for existing in kept:
            existing_set = set(existing)
            overlap = len(route_set & existing_set) / max(len(route_set), 1)
            if overlap > max_overlap:
                duplicate = True
                break
        if not duplicate:
            kept.append(route)
            used_starts[start_id] = used_starts.get(start_id, 0) + 1
    return kept


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
            px_x=px_cx,
            px_y=px_cy,
            depth=hold.depth,
            area=int((hold.bbox.x2 - hold.bbox.x1) * (hold.bbox.y2 - hold.bbox.y1)),
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
    zone_fraction: float = 0.20,
) -> list[list[int]]:
    """Budget-constrained DFS from bottom holds to top holds.

    Uses pixel y for zone classification (image top = low y = wall top).
    Bottom/top zones are defined as fractions of the full image extent
    (max bbox y across all holds), not just the hold y-range.
    """
    ys = [n.px_y for n in graph.nodes.values()]
    y_min, y_max = min(ys), max(ys)
    y_range = y_max  # use full image extent (y=0 is image top)

    zone_thresh = y_range * zone_fraction
    bottom_ids = {nid for nid, n in graph.nodes.items() if n.px_y >= y_max - zone_thresh}
    top_ids    = {nid for nid, n in graph.nodes.items() if n.px_y <= y_min + zone_thresh}

    # Filter starting holds: must be at least 50% of median area (no tiny crimps)
    all_areas = sorted(n.area for n in graph.nodes.values())
    median_area = all_areas[len(all_areas) // 2]
    min_start_area = median_area * 0.5
    pre_filter = len(bottom_ids)
    bottom_ids = {nid for nid in bottom_ids if graph.nodes[nid].area >= min_start_area}
    print(f"[routes] filtered {pre_filter - len(bottom_ids)} small holds from bottom zone (min_area={min_start_area:.0f}px²)", flush=True)

    max_downward_px = y_range * STYLE_PARAMS[style]["max_downward_frac"]
    print(f"[routes] zones: bottom={len(bottom_ids)} holds (y>={y_max - zone_thresh:.0f}), top={len(top_ids)} holds (y<={y_min + zone_thresh:.0f})", flush=True)

    # Cap total DFS iterations to avoid combinatorial explosion on dense graphs.
    MAX_ITERATIONS = 100_000
    results: list[tuple[float, list[int]]] = []
    iterations = 0

    def dfs(cur_id: int, remaining: float, path: list[int], visited: set[int]) -> None:
        nonlocal iterations
        iterations += 1
        if iterations > MAX_ITERATIONS:
            return
        if cur_id in top_ids:
            results.append((remaining, list(path)))
            return
        cur_py = graph.nodes[cur_id].px_y
        for nb_id, cost in graph.adj[cur_id]:
            if iterations > MAX_ITERATIONS:
                return
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
        if iterations > MAX_ITERATIONS:
            break
        dfs(start_id, budget, [start_id], {start_id})

    print(f"[routes] DFS explored {iterations} nodes, found {len(results)} routes (cap={MAX_ITERATIONS})", flush=True)

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
    top_k: int = 50,
    final_k: int = 3,
) -> list[list[int]]:
    """Build climbing routes from a list of detected holds.

    Args:
        holds:      Hold objects with 3D positions and depth from scan_service
        difficulty: "easy" | "medium" | "hard" — sets budget in metres
        style:      "static" | "dynamic" — sets move distance range and alpha
        wingspan:   max reachable distance in metres (caps sparsify mx)
        top_k:      max DFS candidates before Gemini filter
        final_k:   final routes returned
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
    print(f"[routes] full graph: {len(g.nodes)} nodes, {g.edge_count()} directed edges", flush=True)
    _sparsify(g, mn, mx)
    print(f"[routes] after sparsify (mn={mn}, mx={mx}): {g.edge_count()} directed edges", flush=True)
    # Log degree distribution
    degrees = [len(neighbors) for neighbors in g.adj.values()]
    if degrees:
        avg_deg = sum(degrees) / len(degrees)
        max_deg = max(degrees)
        print(f"[routes] avg degree={avg_deg:.1f}, max degree={max_deg}", flush=True)
    candidates = _search_routes(g, budget, style=style, top_k=top_k)
    print(f"[routes] DFS found {len(candidates)} routes", flush=True)

    # Score, dedupe, return top results
    scored = [(_score_route(r, g, style, difficulty), r) for r in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [r for _, r in scored]
    diverse = _dedupe_routes(ranked)
    print(f"[routes] after scoring+dedup: {len(diverse)} diverse routes", flush=True)

    final = diverse[:final_k]

    # Add footholds along each route (post-hoc, doesn't affect pathfinding)
    final = _add_footholds(final, g, wingspan=mx)

    return final


def _add_footholds(
    routes: list[list[int]],
    graph: _Graph,
    wingspan: float,
) -> list[list[int]]:
    """Add footholds along each route.

    For each handhold, find nearby holds below it (within wingspan radius
    in 3D) and randomly insert 1-2 as footholds. Also prepend 1-2 starting
    footholds below the first handhold. This runs after route generation
    so it doesn't affect cost/budget.
    """
    # Foot reach radius: roughly half wingspan (you reach down with your foot)
    foot_radius_3d = wingspan * 0.6

    result: list[list[int]] = []
    for route in routes:
        if len(route) < 2:
            result.append(route)
            continue

        route_set = set(route)
        enriched: list[int] = []

        for idx, hid in enumerate(route):
            hand = graph.nodes[hid]

            # Find candidate footholds: below or near this handhold
            candidates: list[tuple[float, int]] = []
            for nid, node in graph.nodes.items():
                if nid in route_set:
                    continue
                if nid in {fid for fid in enriched if fid not in route_set}:
                    continue  # already used as foothold
                # Must be below or at same height (higher pixel y = lower on wall)
                if node.px_y < hand.px_y:
                    continue
                # Within 3D reach
                dist = _dist3d(hand, node)
                if dist > foot_radius_3d:
                    continue
                candidates.append((dist, nid))

            # Pick footholds for this handhold
            if candidates:
                candidates.sort(key=lambda x: x[0])
                pool = candidates[:5]
                # First handhold: always 1-2 footholds (starting stance)
                # Other handholds: usually 1 foothold, sometimes 2
                if idx == 0:
                    n_feet = random.choice([1, 2])
                else:
                    n_feet = random.choice([1, 1, 1, 2])
                n_feet = min(n_feet, len(pool))
                if n_feet > 0:
                    chosen = random.sample(pool, n_feet)
                    foot_ids = [fid for _, fid in chosen]
                    enriched.extend(foot_ids)

            enriched.append(hid)

        added = len(enriched) - len(route)
        if added > 0:
            print(f"[routes] added {added} foothold(s) to route ({len(route)} → {len(enriched)} holds)", flush=True)
        result.append(enriched)

    return result
