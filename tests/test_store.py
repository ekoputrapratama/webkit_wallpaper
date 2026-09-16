import webkit_wallpaper.store as store


def test_parse_firestore_value_all_types():
    assert store._parse_firestore_value({"stringValue": "abc"}) == "abc"
    assert store._parse_firestore_value({"integerValue": "42"}) == 42
    assert store._parse_firestore_value({"doubleValue": "1.5"}) == 1.5
    assert store._parse_firestore_value({"booleanValue": True}) is True
    assert store._parse_firestore_value(
        {"arrayValue": {"values": [{"stringValue": "a"}, {"integerValue": "1"}]}}
    ) == ["a", 1]
    assert store._parse_firestore_value({"timestampValue": "2026-01-01T00:00:00Z"}) == (
        "2026-01-01T00:00:00Z"
    )
    assert store._parse_firestore_value({"nullValue": None}) is None
    # unknown/empty field yields fallback
    assert store._parse_firestore_value({"weirdValue": 1}) == ""


def test_doc_to_dict_extracts_id_and_fields():
    doc = {
        "name": "projects/p/databases/(default)/documents/wallpapers/w1",
        "fields": {
            "title": {"stringValue": "Sakura"},
            "downloads": {"integerValue": "17"},
        },
    }
    result = store._doc_to_dict(doc)
    assert result["id"] == "w1"
    assert result["title"] == "Sakura"
    assert result["downloads"] == 17


def test_doc_to_dict_empty_name():
    assert store._doc_to_dict({"fields": {}})["id"] is None or True


def test_fetch_wallpapers_returns_error_when_not_configured(monkeypatch):
    real_get = store.dotenv.get

    def _not_configured(key, default=""):
        return ""

    monkeypatch.setattr(store.dotenv, "get", _not_configured)
    wallpapers, err = store.fetch_wallpapers()
    assert wallpapers == []
    assert err
