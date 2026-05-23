import uuid
from datetime import datetime
from unittest.mock import MagicMock

from app.services.mbid_resolution import MbidResolutionService, normalize_name


def test_normalize_name_strips_discogs_numeric_suffix():
    assert normalize_name("Cream (2)") == "Cream"
    assert normalize_name("The Band (13)") == "The Band"


def test_normalize_name_leaves_non_numeric_parentheticals_alone():
    assert normalize_name("Artist (Remastered)") == "Artist (Remastered)"
    assert normalize_name("Beatles, The (Live)") == "Beatles, The (Live)"


def test_normalize_name_leaves_already_clean_names_alone():
    assert normalize_name("Yo La Tengo") == "Yo La Tengo"
    assert normalize_name("Björk") == "Björk"


def test_normalize_name_is_idempotent():
    once = normalize_name("Cream (2)")
    twice = normalize_name(once)
    assert once == twice == "Cream"


def test_normalize_name_strips_trailing_whitespace():
    assert normalize_name("Cream (2)  ") == "Cream"
    assert normalize_name("  Yo La Tengo  ") == "Yo La Tengo"


def test_normalize_name_strips_only_trailing_suffix_not_embedded():
    assert normalize_name("Artist (2) feat. Other") == "Artist (2) feat. Other"


def test_normalize_name_handles_empty_string():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


def test_service_run_resolves_matched_names_leaves_unmatched_null():
    mock_repo = MagicMock()
    mock_repo.find_unresolved_artist_names.return_value = [
        "Yo La Tengo",
        "Cream (2)",
        "Nonexistent",
    ]
    ylt_gid = uuid.uuid4()
    cream_gid = uuid.uuid4()

    def _fake_find(mb_session, normalized):
        return {"Yo La Tengo": ylt_gid, "Cream": cream_gid}.get(normalized)

    mock_repo.find_artist_gid.side_effect = _fake_find
    mock_repo.update_artist_mbids.return_value = 2

    service = MbidResolutionService(repository=mock_repo)
    app_session = MagicMock()
    mb_session = MagicMock()
    user_id = uuid.uuid4()

    result = service.run(app_session, mb_session, user_id)

    assert result["attempted"] == 3
    assert result["resolved"] == 2
    assert result["unmatched"] == 1
    assert "run_at" in result
    datetime.fromisoformat(result["run_at"])

    app_session.commit.assert_called_once()

    call_args = mock_repo.update_artist_mbids.call_args
    assert call_args.args[0] is app_session
    assert call_args.args[1] == user_id
    assert call_args.args[2] == {"Yo La Tengo": ylt_gid, "Cream (2)": cream_gid}


def test_service_run_empty_unresolved_returns_zero_summary():
    mock_repo = MagicMock()
    mock_repo.find_unresolved_artist_names.return_value = []

    service = MbidResolutionService(repository=mock_repo)
    result = service.run(MagicMock(), MagicMock(), uuid.uuid4())

    assert result["attempted"] == 0
    assert result["resolved"] == 0
    assert result["unmatched"] == 0
    mock_repo.find_artist_gid.assert_not_called()
    mock_repo.update_artist_mbids.assert_not_called()


def test_service_run_normalizes_names_before_lookup():
    mock_repo = MagicMock()
    mock_repo.find_unresolved_artist_names.return_value = ["Cream (2)"]
    cream_gid = uuid.uuid4()
    mock_repo.find_artist_gid.return_value = cream_gid
    mock_repo.update_artist_mbids.return_value = 1

    service = MbidResolutionService(repository=mock_repo)
    service.run(MagicMock(), MagicMock(), uuid.uuid4())

    mock_repo.find_artist_gid.assert_called_once()
    assert mock_repo.find_artist_gid.call_args.args[1] == "Cream"

    call_args = mock_repo.update_artist_mbids.call_args
    assert call_args.args[2] == {"Cream (2)": cream_gid}


def test_service_run_does_not_commit_when_no_resolutions():
    mock_repo = MagicMock()
    mock_repo.find_unresolved_artist_names.return_value = ["Nonexistent"]
    mock_repo.find_artist_gid.return_value = None

    service = MbidResolutionService(repository=mock_repo)
    app_session = MagicMock()
    result = service.run(app_session, MagicMock(), uuid.uuid4())

    assert result["attempted"] == 1
    assert result["resolved"] == 0
    mock_repo.update_artist_mbids.assert_not_called()
    app_session.commit.assert_not_called()
