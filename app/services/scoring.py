import math


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


def compute_collaborator_diversity(
    paths: list[dict],
    max_artist_count: int,
) -> float:
    if not paths or max_artist_count <= 1:
        return 0.0
    log_max = math.log(max_artist_count)
    if log_max == 0:
        return 0.0
    scores = []
    for p in paths:
        count = p.get("collaborator_artist_count", 1)
        if count <= 1:
            scores.append(0.0)
        else:
            scores.append(math.log(count) / log_max)
    return sum(scores) / len(scores)


def compute_final_score(
    path_count: int,
    genre_affinity: float,
    collaborator_diversity: float,
    weights: dict[str, float],
) -> float:
    return (
        path_count * weights.get("path_count", 1.0)
        + genre_affinity * weights.get("genre_affinity", 0.5)
        + collaborator_diversity * weights.get("collaborator_diversity", 0.3)
    )
