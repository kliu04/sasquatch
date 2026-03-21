"""
Visualize the hold graph and routes on top of the existing wall image.
Usage: python visualize_graph.py
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Inline graph types (mirrors route_builder.py without import issues)
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: int
    x: float
    y: float


@dataclass
class Graph:
    nodes: dict[int, Node] = field(default_factory=dict)
    adj: dict[int, list[tuple[int, float]]] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        self.adj.setdefault(node.id, [])

    def add_edge(self, a: int, b: int, dist: float) -> None:
        self.adj[a].append((b, dist))
        self.adj[b].append((a, dist))

    def remove_edge(self, a: int, b: int) -> None:
        self.adj[a] = [(n, d) for n, d in self.adj[a] if n != b]
        self.adj[b] = [(n, d) for n, d in self.adj[b] if n != a]

    def edge_count(self) -> int:
        return sum(len(v) for v in self.adj.values()) // 2


def _dist(a: Node, b: Node) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def build_graph(records: list[dict]) -> Graph:
    g = Graph()
    for rec in records:
        cx, cy = rec["mask_centroid"]
        g.add_node(Node(id=rec["instance_id"], x=float(cx), y=float(cy)))
    nodes = list(g.nodes.values())
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            g.add_edge(nodes[i].id, nodes[j].id, _dist(nodes[i], nodes[j]))
    return g


def sparsify(g: Graph, mn: float, mx: float) -> Graph:
    to_remove = [
        (a, b)
        for a, neighbors in g.adj.items()
        for b, d in neighbors
        if a < b and (d < mn or d > mx)
    ]
    for a, b in to_remove:
        g.remove_edge(a, b)
    return g


def search_routes(g: Graph, budget: float, top_k: int = 20, zone: float = 0.15) -> list[list[int]]:
    ys = [n.y for n in g.nodes.values()]
    y_min, y_max = min(ys), max(ys)
    thresh = (y_max - y_min) * zone
    bottom_ids = {nid for nid, n in g.nodes.items() if n.y >= y_max - thresh}
    top_ids    = {nid for nid, n in g.nodes.items() if n.y <= y_min + thresh}

    results: list[tuple[float, list[int]]] = []

    def dfs(cur: int, rem: float, path: list[int], visited: set[int]) -> None:
        if cur in top_ids:
            results.append((rem, list(path)))
            return
        cur_y = g.nodes[cur].y
        for nb, d in g.adj[cur]:
            if nb in visited or g.nodes[nb].y >= cur_y or rem - d < 0:
                continue
            visited.add(nb)
            path.append(nb)
            dfs(nb, rem - d, path, visited)
            path.pop()
            visited.remove(nb)

    for s in bottom_ids:
        dfs(s, budget, [s], {s})

    results.sort(key=lambda x: x[0])
    return [p for _, p in results[:top_k]]


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

COLORS = [
    (0, 100, 255),   # orange-red
    (0, 220, 0),     # green
    (255, 80, 0),    # blue
]


def draw_graph(
    img: np.ndarray,
    g: Graph,
    routes: list[list[int]],
    bottom_ids: set[int],
    top_ids: set[int],
) -> np.ndarray:
    canvas = img.copy()

    # Collect edges that belong to any route
    route_edges: dict[tuple[int, int], int] = {}  # edge -> route index
    for ri, route in enumerate(routes):
        for k in range(len(route) - 1):
            key = (min(route[k], route[k + 1]), max(route[k], route[k + 1]))
            route_edges[key] = ri

    # Draw all sparsified edges in dim gray
    drawn = set()
    for a, neighbors in g.adj.items():
        for b, _ in neighbors:
            key = (min(a, b), max(a, b))
            if key in drawn:
                continue
            drawn.add(key)
            if key in route_edges:
                continue  # draw route edges on top later
            pa = (int(g.nodes[a].x), int(g.nodes[a].y))
            pb = (int(g.nodes[b].x), int(g.nodes[b].y))
            cv2.line(canvas, pa, pb, (80, 80, 80), 1, cv2.LINE_AA)

    # Draw route edges coloured by route
    for edge, ri in route_edges.items():
        a, b = edge
        pa = (int(g.nodes[a].x), int(g.nodes[a].y))
        pb = (int(g.nodes[b].x), int(g.nodes[b].y))
        color = COLORS[ri % len(COLORS)]
        cv2.line(canvas, pa, pb, color, 3, cv2.LINE_AA)

    # Draw nodes
    for nid, node in g.nodes.items():
        cx, cy = int(node.x), int(node.y)
        if nid in bottom_ids:
            node_color = (0, 255, 255)   # yellow — start
        elif nid in top_ids:
            node_color = (255, 0, 255)   # magenta — end
        else:
            node_color = (255, 255, 255) # white — middle
        cv2.circle(canvas, (cx, cy), 12, (0, 0, 0), -1)
        cv2.circle(canvas, (cx, cy), 10, node_color, -1)
        label = str(nid)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.putText(canvas, label, (cx - tw // 2, cy + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

    # Legend
    legend = [
        ("start hold", (0, 255, 255)),
        ("end hold",   (255, 0, 255)),
        ("mid hold",   (255, 255, 255)),
    ]
    for ri, route in enumerate(routes):
        legend.append((f"route {ri + 1} ({len(route)} holds)", COLORS[ri % len(COLORS)]))

    lx, ly = 10, 20
    for text, color in legend:
        cv2.rectangle(canvas, (lx, ly - 10), (lx + 14, ly + 4), color, -1)
        cv2.putText(canvas, text, (lx + 20, ly + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        ly += 22

    return canvas


def main() -> None:
    base = Path(__file__).parent
    preds_path = base / "output/filtered_predictions.json"
    img_path   = base / "demo-data/wall-lidar-scan.png"
    out_path   = base / "output/graph_overlay.png"

    with open(preds_path) as f:
        data = json.load(f)
    records = next(iter(data.values())) if isinstance(data, dict) else data

    MN, MX, BUDGET = 100.0, 400.0, 1500.0

    g = build_graph(records)
    print(f"Full graph:  {len(g.nodes)} nodes, {g.edge_count()} edges")
    sparsify(g, MN, MX)
    print(f"Sparsified:  {g.edge_count()} edges  (mn={MN}, mx={MX})")

    routes = search_routes(g, BUDGET, top_k=3)
    print(f"Routes found: {len(routes)}")
    for i, r in enumerate(routes):
        print(f"  Route {i+1}: {r}")

    # Compute zone sets for colouring
    ys = [n.y for n in g.nodes.values()]
    y_min, y_max = min(ys), max(ys)
    thresh = (y_max - y_min) * 0.15
    bottom_ids = {nid for nid, n in g.nodes.items() if n.y >= y_max - thresh}
    top_ids    = {nid for nid, n in g.nodes.items() if n.y <= y_min + thresh}

    img = cv2.imread(str(img_path))
    if img is None:
        raise FileNotFoundError(f"Could not load image: {img_path}")

    result = draw_graph(img, g, routes, bottom_ids, top_ids)
    cv2.imwrite(str(out_path), result)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
