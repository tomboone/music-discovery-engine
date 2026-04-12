import random


def select_seeds(
    artists: list[dict],
    num_seeds: int,
    exclude_mbids: set[str] | None = None,
) -> list[dict]:
    if not artists:
        return []

    eligible = [
        a for a in artists if a.get("artist_mbid") and a["artist_mbid"] is not None
    ]

    if exclude_mbids:
        eligible = [a for a in eligible if a["artist_mbid"] not in exclude_mbids]

    if not eligible:
        return []

    if len(eligible) <= num_seeds:
        return list(eligible)

    weights = [a.get("playcount", 1) for a in eligible]
    selected: list[dict] = []
    remaining = list(eligible)
    remaining_weights = list(weights)

    while len(selected) < num_seeds and remaining:
        picks = random.choices(remaining, weights=remaining_weights, k=1)
        pick = picks[0]
        if pick not in selected:
            selected.append(pick)
            idx = remaining.index(pick)
            remaining.pop(idx)
            remaining_weights.pop(idx)

    return selected
