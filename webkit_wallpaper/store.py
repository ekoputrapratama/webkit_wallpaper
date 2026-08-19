import json
import threading
import urllib.parse
import urllib.request

from webkit_wallpaper import dotenv

FIRESTORE_BASE = "https://firestore.googleapis.com/v1"
COLLECTION = "wallpapers"


def _parse_firestore_value(field):
    if "stringValue" in field:
        return field["stringValue"]
    if "integerValue" in field:
        return int(field["integerValue"])
    if "doubleValue" in field:
        return float(field["doubleValue"])
    if "booleanValue" in field:
        return field["booleanValue"]
    if "arrayValue" in field:
        return [
            _parse_firestore_value(v)
            for v in field["arrayValue"].get("values", [])
        ]
    if "timestampValue" in field:
        return field["timestampValue"]
    if "nullValue" in field:
        return None
    return ""


def _doc_to_dict(doc):
    result = {"id": doc.get("name", "").rsplit("/", 1)[-1]}
    for key, field in doc.get("fields", {}).items():
        result[key] = _parse_firestore_value(field)
    return result


def fetch_wallpapers(limit=50):
    project_id = dotenv.get("FIREBASE_PROJECT_ID")
    api_key = dotenv.get("FIRESTORE_API_KEY")
    database_id = dotenv.get("FIREBASE_DATABASE_ID", "(default)")

    if not project_id or not api_key or project_id == "your-project-id":
        return [], "Firebase not configured. Set FIREBASE_PROJECT_ID and FIRESTORE_API_KEY in .env"

    encoded_collection = urllib.parse.quote(COLLECTION, safe="")
    encoded_db = urllib.parse.quote(database_id, safe="")
    url = (
        f"{FIRESTORE_BASE}/projects/{project_id}"
        f"/databases/{encoded_db}/documents/{encoded_collection}"
        f"?key={urllib.parse.quote(api_key, safe='')}"
        f"&pageSize={limit}"
    )

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [], f"Failed to fetch wallpapers: {e}"

    wallpapers = []
    for doc in data.get("documents", []):
        wallpapers.append(_doc_to_dict(doc))

    wallpapers.sort(key=lambda w: w.get("downloads", 0), reverse=True)
    return wallpapers, None


def fetch_wallpapers_background(callback, limit=50):
    def _worker():
        wallpapers, error = fetch_wallpapers(limit)
        callback(wallpapers, error)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
