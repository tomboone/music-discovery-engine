import pytest

from app.services.scoring import (
    DEFAULT_BRIDGE_SWEET_SPOTS,
    aggregate_bridge_score,
    compute_bridge_score,
    compute_final_score,
    compute_genre_affinity,
    compute_obscurity,
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


class TestComputeObscurity:
    def test_very_popular_is_low(self):
        result = compute_obscurity(5_000_000, max_listeners=2_000_000)
        assert result == pytest.approx(0.0)

    def test_at_threshold_is_zero(self):
        result = compute_obscurity(2_000_000, max_listeners=2_000_000)
        assert result == pytest.approx(0.0)

    def test_obscure_is_positive(self):
        result = compute_obscurity(50_000, max_listeners=2_000_000)
        assert result > 0.2

    def test_very_obscure_beats_moderately_popular(self):
        obscure = compute_obscurity(10_000, max_listeners=2_000_000)
        popular = compute_obscurity(1_000_000, max_listeners=2_000_000)
        assert obscure > popular

    def test_zero_listeners(self):
        result = compute_obscurity(0, max_listeners=2_000_000)
        assert result == pytest.approx(1.0)

    def test_zero_max(self):
        result = compute_obscurity(500_000, max_listeners=0)
        assert result == pytest.approx(1.0)


class TestComputeFinalScore:
    def test_default_weights(self):
        result = compute_final_score(
            path_count=3,
            genre_affinity=0.5,
            bridge_score=0.4,
            obscurity=0.6,
            weights={
                "path_count": 1.0,
                "genre_affinity": 0.5,
                "bridge_score": 1.0,
                "obscurity": 0.5,
            },
        )
        expected = 3 * 1.0 + 0.5 * 0.5 + 0.4 * 1.0 + 0.6 * 0.5
        assert result == pytest.approx(expected)

    def test_zero_weights(self):
        result = compute_final_score(
            path_count=3,
            genre_affinity=0.8,
            bridge_score=0.6,
            obscurity=0.5,
            weights={
                "path_count": 0.0,
                "genre_affinity": 0.0,
                "bridge_score": 0.0,
                "obscurity": 0.0,
            },
        )
        assert result == pytest.approx(0.0)

    def test_path_count_only(self):
        result = compute_final_score(
            path_count=2,
            genre_affinity=0.9,
            bridge_score=0.8,
            obscurity=0.7,
            weights={
                "path_count": 1.0,
                "genre_affinity": 0.0,
                "bridge_score": 0.0,
                "obscurity": 0.0,
            },
        )
        assert result == pytest.approx(2.0)

    def test_great_bridge_competes_with_extra_path(self):
        """A single-path candidate with a perfect bridge should score
        competitively with a two-path candidate with a weak bridge."""
        weights = {
            "path_count": 1.0,
            "genre_affinity": 0.0,
            "bridge_score": 1.0,
            "obscurity": 0.0,
        }
        single_path_great_bridge = compute_final_score(
            path_count=1,
            genre_affinity=0,
            bridge_score=1.0,
            obscurity=0,
            weights=weights,
        )
        two_path_weak_bridge = compute_final_score(
            path_count=2,
            genre_affinity=0,
            bridge_score=0.1,
            obscurity=0,
            weights=weights,
        )
        # 1 + 1.0 = 2.0  vs  2 + 0.1 = 2.1 — close, two-path still edges out
        assert abs(single_path_great_bridge - two_path_weak_bridge) < 0.5


class TestComputeBridgeScore:
    def test_count_one_returns_zero(self):
        assert compute_bridge_score(1, "producer") == pytest.approx(0.0)

    def test_count_zero_returns_zero(self):
        assert compute_bridge_score(0, "producer") == pytest.approx(0.0)

    def test_peaks_at_sweet_spot(self):
        # Producer sweet spot is 50; score at 50 should be max (1.0)
        at_peak = compute_bridge_score(50, "producer")
        assert at_peak == pytest.approx(1.0)

    def test_falls_off_above_sweet_spot(self):
        # Greg Calbi case — promiscuous collaborator
        at_peak = compute_bridge_score(50, "producer")
        too_high = compute_bridge_score(5000, "producer")
        assert too_high < at_peak
        assert too_high < 0.5

    def test_falls_off_below_sweet_spot(self):
        # Tiny scene collaborator
        at_peak = compute_bridge_score(50, "producer")
        too_low = compute_bridge_score(3, "producer")
        assert too_low < at_peak
        assert too_low < 0.5

    def test_per_relationship_sweet_spots_differ(self):
        # Instrument sweet spot (150) is higher than producer (50)
        # so 150 should score higher for instrument than for producer
        instrument_score = compute_bridge_score(150, "instrument")
        producer_score = compute_bridge_score(150, "producer")
        assert instrument_score > producer_score
        assert instrument_score == pytest.approx(1.0)

    def test_unknown_relationship_uses_default(self):
        # Unknown rel type should use _default sweet spot (100)
        score = compute_bridge_score(100, "remixer")
        assert score == pytest.approx(1.0)

    def test_monotonic_increase_below_peak(self):
        # On the rising side of the bell
        a = compute_bridge_score(5, "producer")
        b = compute_bridge_score(15, "producer")
        c = compute_bridge_score(40, "producer")
        assert a < b < c

    def test_monotonic_decrease_above_peak(self):
        # On the falling side of the bell (producer peak = 50)
        a = compute_bridge_score(60, "producer")
        b = compute_bridge_score(200, "producer")
        c = compute_bridge_score(2000, "producer")
        assert a > b > c

    def test_custom_sweet_spots_override(self):
        custom = {"_default": 10, "producer": 10}
        peak = compute_bridge_score(10, "producer", sweet_spots=custom)
        off = compute_bridge_score(50, "producer", sweet_spots=custom)
        assert peak > off

    def test_default_sweet_spots_constant_shape(self):
        assert DEFAULT_BRIDGE_SWEET_SPOTS["producer"] == 50
        assert DEFAULT_BRIDGE_SWEET_SPOTS["instrument"] == 150
        assert DEFAULT_BRIDGE_SWEET_SPOTS["performer"] == 150
        assert DEFAULT_BRIDGE_SWEET_SPOTS["vocal"] == 100
        assert DEFAULT_BRIDGE_SWEET_SPOTS["_default"] == 100


class TestAggregateBridgeScore:
    def test_empty_paths_returns_zero(self):
        assert aggregate_bridge_score([]) == pytest.approx(0.0)

    def test_single_perfect_path(self):
        paths = [
            {"relationship_type": "producer", "collaborator_artist_count": 50},
        ]
        assert aggregate_bridge_score(paths) == pytest.approx(1.0)

    def test_mean_across_paths(self):
        # Two paths, one perfect (producer at 50) and one with count=1 (zero)
        paths = [
            {"relationship_type": "producer", "collaborator_artist_count": 50},
            {"relationship_type": "instrument", "collaborator_artist_count": 1},
        ]
        result = aggregate_bridge_score(paths)
        assert result == pytest.approx(0.5)

    def test_missing_relationship_type_uses_default(self):
        paths = [{"collaborator_artist_count": 100}]
        # _default sweet spot is 100, so a count of 100 should peak
        assert aggregate_bridge_score(paths) == pytest.approx(1.0)

    def test_missing_count_treated_as_one(self):
        paths = [{"relationship_type": "producer"}]
        assert aggregate_bridge_score(paths) == pytest.approx(0.0)

    def test_custom_sweet_spots_passed_through(self):
        paths = [{"relationship_type": "producer", "collaborator_artist_count": 10}]
        custom = {"_default": 10, "producer": 10}
        assert aggregate_bridge_score(paths, sweet_spots=custom) == pytest.approx(1.0)
