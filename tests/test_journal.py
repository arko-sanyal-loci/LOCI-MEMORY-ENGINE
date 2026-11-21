import sqlite3

import pytest

from rag.journal import ConsentRequired, RagAppendixJournal


def make_journal(tmp_path):
    return RagAppendixJournal(str(tmp_path / "appendix.sqlite3"), half_life_days=30)


def test_profile_collection_is_off_until_explicit_consent(tmp_path):
    journal = make_journal(tmp_path)
    try:
        with pytest.raises(ConsentRequired):
            journal.append_features("user", {"routine": "morning"}, source="audio")
        assert journal.verify_chain()["entries"] == 0
    finally:
        journal.close()


def test_features_build_versioned_heat_profile_and_hash_chain(tmp_path):
    journal = make_journal(tmp_path)
    try:
        journal.grant_consent("environment", occurred_at=100)
        for at in (100, 200, 300):
            journal.append_features("environment", {"noise": "quiet", "light": 0.5},
                                    source="av_features", occurred_at=at)
        profile_event = journal.build_profile("environment", now=300)
        assert profile_event["event_type"] == "profile_version"
        profile = journal.get_profile("environment")
        assert profile["observation_count"] == 3
        assert {(item["feature"], item["value"]) for item in profile["patterns"]} == {
            ("noise", "quiet"), ("light", "num_0p500")
        }
        assert all(item["support"] == 3 and item["confidence"] >= 0.60
                   for item in profile["patterns"])
        assert journal.verify_chain()["valid"] is True
    finally:
        journal.close()


def test_revocation_hides_profile_and_new_consent_starts_new_epoch(tmp_path):
    journal = make_journal(tmp_path)
    try:
        journal.grant_consent("user", occurred_at=10)
        for at in (11, 12, 13):
            journal.append_features("user", {"breaks": "regular"}, source="interaction",
                                    occurred_at=at)
        journal.build_profile("user", now=14)
        journal.revoke_consent("user", occurred_at=15)
        assert journal.get_profile("user") is None
        with pytest.raises(ConsentRequired):
            journal.append_features("user", {"breaks": "regular"}, source="interaction")
        journal.grant_consent("user", occurred_at=20)
        assert journal.get_profile("user") is None
        assert journal.build_profile("user", now=21) is None
        assert journal.consent_status()["user"]["consent_version"] == 2
        assert journal.verify_chain()["valid"] is True
    finally:
        journal.close()


def test_journal_rejects_free_text_and_mutation(tmp_path):
    journal = make_journal(tmp_path)
    try:
        journal.grant_consent("user", occurred_at=1)
        with pytest.raises(ValueError, match="categorical token"):
            journal.append_features("user", {"comment": "my private conversation"},
                                    source="interaction")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            journal.conn.execute("UPDATE journal_events SET payload_json='{}' WHERE seq=1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            journal.conn.execute("DELETE FROM journal_events WHERE seq=1")
        assert journal.verify_chain()["valid"] is True
    finally:
        journal.close()


def test_profile_scopes_are_isolated(tmp_path):
    journal = make_journal(tmp_path)
    try:
        journal.grant_consent("environment", occurred_at=1)
        for at in (2, 3, 4):
            journal.append_features("environment", {"noise": "quiet"}, source="av_features",
                                    occurred_at=at)
        assert journal.build_profile("environment", now=4) is not None
        assert journal.get_profile("user") is None
    finally:
        journal.close()


def test_audio_video_adapter_requires_environment_consent_and_drops_text(tmp_path):
    journal = make_journal(tmp_path)
    audio = {"track": "audio", "pts_us": 1_000_000,
             "data": {"rms": 0.04, "spectral_centroid_hz": 900}}
    try:
        with pytest.raises(ConsentRequired):
            journal.append_stream_event(audio, session_started_at=100)
        journal.grant_consent("environment", occurred_at=100)
        row = journal.append_stream_event(audio, session_started_at=100)
        assert row["occurred_at"] == 101
        assert journal.append_stream_event({"track": "caption", "pts_us": 0,
                                            "data": {"text": "private transcript"}}) is None
        video = {"track": "video", "pts_us": 2_000_000,
                 "data": {"object_id": "subject-123", "fidelity": "hot",
                          "change_reasons": ["focus"],
                          "families": {"motion": {"screen_speed": 0.2}}}}
        journal.append_stream_event(video, session_started_at=100)
        entries = journal.conn.execute(
            "SELECT payload_json FROM journal_events WHERE event_type='feature_observation'"
        ).fetchall()
        payloads = [row[0] for row in entries]
        assert all("subject-123" not in payload for payload in payloads)
        assert all("private transcript" not in payload for payload in payloads)
        assert journal.verify_chain()["valid"] is True
    finally:
        journal.close()
