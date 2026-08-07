"""Who shares a scene with whom.

A screenplay is a graph whether or not anyone draws it: every scene puts a set
of people in a room, and the pattern of those rooms is the shape of the story.
Two people who never appear together have no relationship the audience can
watch, however much the script talks about one to the other.

What this module computes, all of it arithmetic over the parse:

  * **Edges.** Two speaking parts share an edge when they speak in the same
    scene. Weight is how many scenes.
  * **Components.** A set of people connected to each other and to nobody
    else. A feature whose cast falls into two components has two casts, and
    that is almost always a merge that never happened.
  * **Cut vertices.** Someone whose removal splits the cast in two: the only
    person carrying information between two groups. Not a defect, and often
    the point of the character, which is why it is reported as a number and
    never as a finding.
  * **Weighted degree.** How much of the cast someone actually plays against,
    which is a different question from how many lines they have. A lead with
    a high line count and a low degree is talking to the same one person all
    film.

Scene co-presence uses speaking parts only, because a cue is the one thing on
the page that is unambiguous about who is in the room. A silent character
named in an action line is present to the audience and invisible here, which
is a known and deliberate floor on recall.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations

from .models import Script


@dataclass
class Edge:
    a: str
    b: str
    scenes: list[int] = field(default_factory=list)

    @property
    def weight(self) -> int:
        return len(self.scenes)


@dataclass
class Node:
    name: str
    degree: int = 0                 # distinct people shared a scene with
    weighted_degree: int = 0        # scenes shared, summed over those people
    scenes: int = 0                 # scenes they speak in
    component: int = 0
    cut_vertex: bool = False
    reach: float = 0.0              # share of the rest of the cast played against


@dataclass
class CharacterNetwork:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    components: list[list[str]] = field(default_factory=list)

    @property
    def cast(self) -> int:
        return len(self.nodes)

    @property
    def density(self) -> float:
        """Edges present over edges possible. How connected the ensemble is."""
        possible = self.cast * (self.cast - 1) / 2
        return round(len(self.edges) / possible, 3) if possible else 0.0

    @property
    def isolated(self) -> list[str]:
        """Speaking parts who never share a scene with another speaking part."""
        return [n.name for n in self.nodes if n.degree == 0]

    @property
    def cut_vertices(self) -> list[str]:
        return [n.name for n in self.nodes if n.cut_vertex]

    def to_dict(self) -> dict:
        return {
            "cast": self.cast,
            "density": self.density,
            "components": self.components,
            "isolated": self.isolated,
            "cut_vertices": self.cut_vertices,
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [{"a": e.a, "b": e.b, "weight": e.weight, "scenes": e.scenes}
                      for e in self.edges],
        }


def _adjacency(edges: list[Edge]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e.a, set()).add(e.b)
        adj.setdefault(e.b, set()).add(e.a)
    return adj


def _components(names: list[str], adj: dict[str, set[str]]) -> list[list[str]]:
    """Connected components, in the order their first member appears."""
    seen: set[str] = set()
    out: list[list[str]] = []
    for name in names:
        if name in seen:
            continue
        stack, group = [name], []
        seen.add(name)
        while stack:
            cur = stack.pop()
            group.append(cur)
            for nxt in sorted(adj.get(cur, ())):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(sorted(group))
    return out


def _cut_vertices(names: list[str], adj: dict[str, set[str]]) -> set[str]:
    """Nodes whose removal splits the cast further than it was already split.

    Removing any node drops the component count by one when that node stood
    alone, and leaves it unchanged when the node was a leaf. Only a node that
    was holding two groups together pushes the count ABOVE where it started,
    which is why the test is a plain `>`.

    Done by removing each node and recounting rather than by Tarjan's linear
    algorithm. A cast is tens of names, so the quadratic version costs nothing
    measurable and can be checked by reading it, which is worth more here than
    the asymptotics.
    """
    base = len(_components(names, adj))
    out: set[str] = set()
    for name in names:
        rest = [n for n in names if n != name]
        pruned = {n: adj.get(n, set()) - {name} for n in rest}
        if len(_components(rest, pruned)) > base:
            out.add(name)
    return out


def build(script: Script) -> CharacterNetwork:
    """The co-presence graph for one script."""
    registry = script.character_registry()
    names = sorted(registry)
    if not names:
        return CharacterNetwork()

    pairs: dict[tuple[str, str], list[int]] = {}
    for sc in script.scenes:
        present = sorted(set(sc.characters) & set(registry))
        for a, b in combinations(present, 2):
            pairs.setdefault((a, b), []).append(sc.index)

    edges = [Edge(a, b, scenes) for (a, b), scenes in
             sorted(pairs.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    adj = _adjacency(edges)
    weighted: dict[str, int] = {}
    for e in edges:
        weighted[e.a] = weighted.get(e.a, 0) + e.weight
        weighted[e.b] = weighted.get(e.b, 0) + e.weight

    components = _components(names, adj)
    where = {name: i for i, group in enumerate(components) for name in group}
    cuts = _cut_vertices(names, adj)

    nodes = [
        Node(name=name, degree=len(adj.get(name, ())), weighted_degree=weighted.get(name, 0),
             scenes=len(registry[name]), component=where[name], cut_vertex=name in cuts,
             reach=round(len(adj.get(name, ())) / max(len(names) - 1, 1), 3))
        for name in names
    ]
    nodes.sort(key=lambda n: (-n.weighted_degree, -n.degree, n.name))
    return CharacterNetwork(nodes=nodes, edges=edges, components=components)
