from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field


@dataclass
class Node:
    id: int
    x: float
    y: float
    score: float = 0.0
    area: int = 0


@dataclass
class Graph:
    nodes: dict[int, Node] = field(default_factory=dict)
    # adjacency: node_id -> list of (neighbor_id, distance)
    adj: dict[int, list[tuple[int, float]]] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        if node.id not in self.adj:
            self.adj[node.id] = []

    def add_edge(self, a: int, b: int, dist: float) -> None:
        self.adj[a].append((b, dist))
        self.adj[b].append((a, dist))

    def remove_edge(self, a: int, b: int) -> None:
        self.adj[a] = [(n, d) for n, d in self.adj[a] if n != b]
        self.adj[b] = [(n, d) for n, d in self.adj[b] if n != a]

    def edge_count(self) -> int:
        return sum(len(neighbors) for neighbors in self.adj.values()) // 2


def _dist(a: Node, b: Node) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def build_graph(records: list[dict]) -> Graph:
    """Pass 1: Build a fully connected graph from detection records."""
    g = Graph()
    for rec in records:
        cx, cy = rec["mask_centroid"]
        node = Node(
            id=rec["instance_id"],
            x=float(cx),
            y=float(cy),
            score=rec.get("score", 0.0),
            area=rec.get("mask_area_px", 0),
        )
        g.add_node(node)

    node_list = list(g.nodes.values())
    for i in range(len(node_list)):
        for j in range(i + 1, len(node_list)):
            a, b = node_list[i], node_list[j]
            g.add_edge(a.id, b.id, _dist(a, b))

    return g


def sparsify(graph: Graph, mn: float, mx: float) -> Graph:
    """Pass 2: Remove edges with distance < mn or distance > mx."""
    edges_to_remove = []
    for node_id, neighbors in graph.adj.items():
        for neighbor_id, dist in neighbors:
            if node_id < neighbor_id and (dist < mn or dist > mx):
                edges_to_remove.append((node_id, neighbor_id))

    for a, b in edges_to_remove:
        graph.remove_edge(a, b)

    return graph


def search_routes(
    graph: Graph,
    budget: float,
    top_k: int = 20,
    zone_fraction: float = 0.15,
) -> list[list[int]]:
    """Pass 3: DFS from bottom holds to top holds, constrained by budget.

    Upward-only movement: only traverse to nodes with strictly lower y value.
    Collects paths that reach a top node, sorted by how close remaining budget is to 0.
    Returns top_k routes.
    """
    ys = [n.y for n in graph.nodes.values()]
    y_min, y_max = min(ys), max(ys)
    y_range = y_max - y_min

    threshold = y_range * zone_fraction
    bottom_ids = {nid for nid, n in graph.nodes.items() if n.y >= y_max - threshold}
    top_ids = {nid for nid, n in graph.nodes.items() if n.y <= y_min + threshold}

    all_paths: list[tuple[float, list[int]]] = []  # (remaining_budget, path)

    def dfs(current_id: int, remaining: float, path: list[int], visited: set[int]) -> None:
        if remaining < 0:
            return
        if current_id in top_ids:
            all_paths.append((remaining, list(path)))
            return

        current_y = graph.nodes[current_id].y
        for neighbor_id, dist in graph.adj[current_id]:
            if neighbor_id in visited:
                continue
            # Upward only: neighbor must have lower y (higher on wall)
            if graph.nodes[neighbor_id].y >= current_y:
                continue
            if remaining - dist < 0:
                continue
            visited.add(neighbor_id)
            path.append(neighbor_id)
            dfs(neighbor_id, remaining - dist, path, visited)
            path.pop()
            visited.remove(neighbor_id)

    for start_id in bottom_ids:
        dfs(start_id, budget, [start_id], {start_id})

    # Sort by remaining budget closest to 0 (most budget-exact routes first)
    all_paths.sort(key=lambda p: p[0])
    return [path for _, path in all_paths[:top_k]]


def filter_routes_gemini(routes: list[list[int]], k: int = 3) -> list[list[int]]:
    """Pass 4: Stub — Gemini will pick the top k routes from candidates."""
    return routes[:k]


def build_routes(
    records: list[dict],
    mn: float,
    mx: float,
    budget: float,
    top_k: int = 20,
    gemini_k: int = 3,
) -> list[list[int]]:
    """Run all 4 passes and return the final filtered routes."""
    g = build_graph(records)
    print(f"[build_graph]  nodes={len(g.nodes)}, edges={g.edge_count()}")

    sparsify(g, mn, mx)
    print(f"[sparsify]     nodes={len(g.nodes)}, edges={g.edge_count()} (mn={mn}, mx={mx})")

    candidates = search_routes(g, budget, top_k=top_k)
    print(f"[search_dfs]   found {len(candidates)} candidate routes")

    routes = filter_routes_gemini(candidates, k=gemini_k)
    print(f"[filter_gemini] returning {len(routes)} routes")

    return routes


def _load_records(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    # Support both flat list and {image_name: [...]} format
    if isinstance(data, list):
        return data
    # Take all records from all images
    records = []
    for v in data.values():
        records.extend(v)
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build climbing routes from hold detections")
    parser.add_argument("predictions", help="Path to filtered_predictions.json")
    parser.add_argument("--mn", type=float, default=100.0, help="Min edge distance (sparsify)")
    parser.add_argument("--mx", type=float, default=400.0, help="Max edge distance (sparsify)")
    parser.add_argument("--budget", type=float, default=1500.0, help="Difficulty budget for DFS")
    parser.add_argument("--top-k", type=int, default=20, help="Max candidate routes from DFS")
    parser.add_argument("--gemini-k", type=int, default=3, help="Final routes to return")
    args = parser.parse_args()

    records = _load_records(args.predictions)
    routes = build_routes(records, args.mn, args.mx, args.budget, args.top_k, args.gemini_k)

    print("\nFinal routes (hold IDs):")
    for i, route in enumerate(routes):
        print(f"  Route {i + 1}: {route}")
