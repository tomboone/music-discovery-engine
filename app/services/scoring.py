import math

DEFAULT_BRIDGE_SWEET_SPOTS = {
    "producer": 50,
    "instrument": 150,
    "performer": 150,
    "vocal": 100,
    "_default": 100,
}
DEFAULT_BRIDGE_FALLOFF = 1.5  # standard deviation in log-units


def compute_bridge_score(
    count: int,
    relationship_type: str,
    sweet_spots: dict[str, int] | None = None,
    falloff: float = DEFAULT_BRIDGE_FALLOFF,
) -> float:
    """Score a single collaborator path by how well it bridges scenes.

    Bell-shaped on log(collaborator_artist_count):
      - count <= 1: 0.0 (no network)
      - count ≈ sweet_spot[rel_type]: peaks at 1.0
      - count >> sweet_spot: drops back toward 0.0 (promiscuous = low signal)
    """
    if count <= 1:
        return 0.0
    spots = sweet_spots or DEFAULT_BRIDGE_SWEET_SPOTS
    target = spots.get(relationship_type, spots["_default"])
    distance = abs(math.log(count) - math.log(target))
    return math.exp(-(distance**2) / (2 * falloff**2))


def aggregate_bridge_score(
    paths: list[dict],
    sweet_spots: dict[str, int] | None = None,
    falloff: float = DEFAULT_BRIDGE_FALLOFF,
) -> float:
    """Mean bridge score across all paths for a candidate."""
    if not paths:
        return 0.0
    scores = [
        compute_bridge_score(
            p.get("collaborator_artist_count", 1),
            p.get("relationship_type", "_default"),
            sweet_spots=sweet_spots,
            falloff=falloff,
        )
        for p in paths
    ]
    return sum(scores) / len(scores)


def compute_genre_affinity(
    seed_tags: dict[str, int],
    candidate_tags: dict[str, int],
) -> float:
    if not seed_tags or not candidate_tags:
        return 0.0
    seed_total = sum(seed_tags.values())
    if seed_total == 0:
        return 0.0
    shared_weight = sum(
        min(seed_tags[tag], candidate_tags[tag])
        for tag in seed_tags
        if tag in candidate_tags
    )
    return shared_weight / seed_total


def compute_obscurity(listeners: int, max_listeners: int) -> float:
    """Score from 0.0 (very popular) to 1.0 (very obscure).
    Uses inverse log scale so the penalty is steep for mega-stars
    but gentle for moderately popular artists."""
    if max_listeners <= 0 or listeners <= 0:
        return 1.0
    if listeners >= max_listeners:
        return 0.0
    # Inverse log: obscure artists score high, popular ones score low
    return 1.0 - math.log(listeners) / math.log(max_listeners)


def compute_final_score(
    path_count: int,
    genre_affinity: float,
    bridge_score: float,
    obscurity: float,
    weights: dict[str, float],
) -> float:
    return (
        path_count * weights.get("path_count", 1.0)
        + genre_affinity * weights.get("genre_affinity", 0.5)
        + bridge_score * weights.get("bridge_score", 1.0)
        + obscurity * weights.get("obscurity", 0.5)
    )
