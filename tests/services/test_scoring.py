import pytest

from app.services.scoring import (
    compute_collaborator_diversity,
    compute_final_score,
    compute_genre_affinity,
)


class TestComputeGenreAffinity:
    def test_full_overlap(self):
        seed = {"indie rock": 9, "dream pop": 6}
        candidate = {"indie rock": 9, "dream pop": 6}
        result = compute_genre_affinity(seed, candidate)
        assert result == pytest.approx(1.0)

    def test_partial_overlap(self):
        seed = {"indie rock": 9, "dream pop": 6, "noise pop": 5}
        candidate = {"indie rock": 5, "jazz": 10}
        result = compute_genre_affinity(seed, candidate)
        assert result == pytest.approx(5 / 20)

    def test_no_overlap(self):
        seed = {"indie rock": 9}
        candidate = {"jazz": 10}
        result = compute_genre_affinity(seed, candidate)
        assert result == pytest.approx(0.0)

    def test_empty_seed_tags(self):
        result = compute_genre_affinity({}, {"jazz": 10})
        assert result == pytest.approx(0.0)

    def test_empty_candidate_tags(self):
        result = compute_genre_affinity({"indie rock": 9}, {})
        assert result == pytest.approx(0.0)

    def test_both_empty(self):
        result = compute_genre_affinity({}, {})
        assert result == pytest.approx(0.0)

    def test_min_count_used(self):
        seed = {"rock": 10}
        candidate = {"rock": 3}
        result = compute_genre_affinity(seed, candidate)
        assert result == pytest.approx(3 / 10)


class TestComputeCollaboratorDiversity:
    def test_high_diversity(self):
        paths = [
            {"collaborator_artist_count": 30},
            {"collaborator_artist_count": 25},
        ]
        result = compute_collaborator_diversity(paths, max_artist_count=30)
        assert 0.0 < result <= 1.0

    def test_low_diversity(self):
        paths = [
            {"collaborator_artist_count": 2},
        ]
        result = compute_collaborator_diversity(paths, max_artist_count=30)
        assert 0.0 < result < 0.5

    def test_high_beats_low(self):
        high = compute_collaborator_diversity(
            [{"collaborator_artist_count": 30}], max_artist_count=30
        )
        low = compute_collaborator_diversity(
            [{"collaborator_artist_count": 2}], max_artist_count=30
        )
        assert high > low

    def test_empty_paths(self):
        result = compute_collaborator_diversity([], max_artist_count=30)
        assert result == pytest.approx(0.0)

    def test_max_artist_count_zero(self):
        paths = [{"collaborator_artist_count": 5}]
        result = compute_collaborator_diversity(paths, max_artist_count=0)
        assert result == pytest.approx(0.0)

    def test_collaborator_count_one(self):
        paths = [{"collaborator_artist_count": 1}]
        result = compute_collaborator_diversity(paths, max_artist_count=30)
        assert result == pytest.approx(0.0)


class TestComputeFinalScore:
    def test_default_weights(self):
        result = compute_final_score(
            path_count=3,
            genre_affinity=0.5,
            collaborator_diversity=0.4,
            weights={
                "path_count": 1.0,
                "genre_affinity": 0.5,
                "collaborator_diversity": 0.3,
            },
        )
        expected = 3 * 1.0 + 0.5 * 0.5 + 0.4 * 0.3
        assert result == pytest.approx(expected)

    def test_zero_weights(self):
        result = compute_final_score(
            path_count=3,
            genre_affinity=0.8,
            collaborator_diversity=0.6,
            weights={
                "path_count": 0.0,
                "genre_affinity": 0.0,
                "collaborator_diversity": 0.0,
            },
        )
        assert result == pytest.approx(0.0)

    def test_path_count_only(self):
        result = compute_final_score(
            path_count=2,
            genre_affinity=0.9,
            collaborator_diversity=0.8,
            weights={
                "path_count": 1.0,
                "genre_affinity": 0.0,
                "collaborator_diversity": 0.0,
            },
        )
        assert result == pytest.approx(2.0)
