"""End-to-end API tests using SQLite and mocked GCS.

Run with: PYTHONPATH=.:hold-detector .venv/bin/python tests/test_api.py
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup paths
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "hold-detector"))

# Use SQLite for testing
os.environ["DATABASE_URL"] = "sqlite:///test_sasquatch.db"

# Override db module to use SQLite BEFORE any other imports
import database.db as db_mod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///test_sasquatch.db", connect_args={"check_same_thread": False})
db_mod.engine = engine
db_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from database.schema import Base, User

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

# Mock auth to bypass Google OAuth
import database.auth as auth_mod


def mock_get_current_user(authorization: str = "Bearer test", db=None):
    db_session = db or db_mod.SessionLocal()
    user = db_session.query(User).filter(User.google_id == "test_user").first()
    if not user:
        user = User(google_id="test_user", username="TestUser", wingspan=1.75)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


auth_mod.get_current_user = mock_get_current_user

# Mock GCS storage and ScanWorker
mock_storage = MagicMock()
mock_storage.generate_upload_url.return_value = "https://storage.googleapis.com/test-signed-url"
mock_storage.public_url.return_value = "https://storage.googleapis.com/test/file.png"
mock_storage.upload_bytes.return_value = "https://storage.googleapis.com/test/uploaded.png"
mock_storage.download_to_tempfile.return_value = Path("/tmp/test.ply")
mock_storage.delete_prefix.return_value = None

mock_worker = MagicMock()
mock_worker.generate_routes.return_value = ([[0, 1, 2]], [b"fake_png_data"])
mock_worker.wait_for_ready = MagicMock(return_value="ready")

with patch("database.server.GCSStorage", return_value=mock_storage), \
     patch("database.server.ScanWorker", return_value=mock_worker):
    from database.server import app

from database.routers import climbs, walls

walls.configure(mock_storage, mock_worker)
climbs.configure(mock_storage, mock_worker)

from fastapi.testclient import TestClient

client = TestClient(app)
HEADERS = {"Authorization": "Bearer test"}

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")


def simulate_ready_wall():
    from database.schema import Wall, WallStatus

    db = db_mod.SessionLocal()
    wall = Wall(
        user_id=1,
        name="Ready Wall",
        status=WallStatus.ready,
        hold_count=3,
        holds_json=json.dumps([
            {"id": 0, "position": {"x": 0.5, "y": 0.5, "z": 0.1}, "bbox": {"x1": 100, "y1": 400, "x2": 150, "y2": 450}, "confidence": 0.95, "depth": 0.03},
            {"id": 1, "position": {"x": 0.6, "y": 1.0, "z": 0.1}, "bbox": {"x1": 120, "y1": 300, "x2": 170, "y2": 350}, "confidence": 0.92, "depth": 0.04},
            {"id": 2, "position": {"x": 0.4, "y": 1.5, "z": 0.1}, "bbox": {"x1": 80, "y1": 200, "x2": 130, "y2": 250}, "confidence": 0.88, "depth": 0.05},
        ]),
        wall_img_url="https://storage.googleapis.com/test/wall.png",
        holds_image_url="https://storage.googleapis.com/test/holds.png",
    )
    db.add(wall)
    db.commit()
    db.refresh(wall)
    wid = wall.id
    db.close()
    return wid


def test_health():
    print("\n[Health]")
    r = client.get("/health")
    check("returns 200", r.status_code == 200)
    check("body is ok", r.json() == {"status": "ok"})


def test_user_profile():
    print("\n[User Profile]")
    r = client.get("/users/me", headers=HEADERS)
    check("GET /users/me returns 200", r.status_code == 200)
    check("has username", r.json()["username"] == "TestUser")
    check("has wingspan", r.json()["wingspan"] == 1.75)

    r = client.patch("/users/me", headers=HEADERS, json={"wingspan": 1.85, "username": "Randy"})
    check("PATCH /users/me returns 200", r.status_code == 200)
    check("wingspan updated", r.json()["wingspan"] == 1.85)
    check("username updated", r.json()["username"] == "Randy")


def test_wall_lifecycle():
    print("\n[Wall Lifecycle]")
    # Create
    r = client.post("/walls", headers=HEADERS, json={"name": "Test Wall"})
    check("POST /walls returns 201", r.status_code == 201)
    data = r.json()
    check("status is pending_upload", data["status"] == "pending_upload")
    check("has ply_upload_url", "ply_upload_url" in data)
    check("has png_upload_url", "png_upload_url" in data)
    wall_id = data["id"]

    # List
    r = client.get("/walls", headers=HEADERS)
    check("GET /walls returns 200", r.status_code == 200)
    check("has walls", len(r.json()) >= 1)

    # Get
    r = client.get(f"/walls/{wall_id}", headers=HEADERS)
    check("GET /walls/{id} returns 200", r.status_code == 200)
    check("correct id", r.json()["id"] == wall_id)

    # Not found
    r = client.get("/walls/99999", headers=HEADERS)
    check("nonexistent wall returns 404", r.status_code == 404)

    return wall_id


def test_error_before_ready(wall_id):
    print("\n[Error Before Ready]")
    r = client.get(f"/walls/{wall_id}/holds", headers=HEADERS)
    check("holds before ready returns 409", r.status_code == 409)

    r = client.post(f"/walls/{wall_id}/climbs", headers=HEADERS, json={"difficulty": "medium", "style": "static"})
    check("climbs before ready returns 409", r.status_code == 409)


def test_process(wall_id):
    print("\n[Process Wall]")
    r = client.post(f"/walls/{wall_id}/process", headers=HEADERS)
    check("process returns 202", r.status_code == 202)
    check("status is processing", r.json()["status"] == "processing")

    r = client.post(f"/walls/{wall_id}/process", headers=HEADERS)
    check("re-process returns 409", r.status_code == 409)


def test_holds():
    print("\n[Holds]")
    wid = simulate_ready_wall()
    r = client.get(f"/walls/{wid}/holds", headers=HEADERS)
    check("GET /holds returns 200", r.status_code == 200)
    data = r.json()
    check("has 3 holds", len(data["holds"]) == 3)
    check("hold has position", "position" in data["holds"][0])
    check("hold has bbox", "bbox" in data["holds"][0])
    check("hold has confidence", "confidence" in data["holds"][0])
    return wid


def test_climb_lifecycle(wall_id):
    print("\n[Climb Lifecycle]")
    # Create climbs
    r = client.post(f"/walls/{wall_id}/climbs", headers=HEADERS, json={"difficulty": "easy", "style": "static", "top_k": 2})
    check("POST /climbs returns 201", r.status_code == 201)
    data = r.json()
    check("returns array", isinstance(data, list))
    check("has climbs", len(data) > 0)

    if not data:
        print("  SKIP: no climbs generated")
        return

    climb = data[0]
    climb_id = climb["id"]
    check("difficulty is easy", climb["difficulty"] == "easy")
    check("classification is static", climb["classification"] == "static")
    check("is_saved is false", climb["is_saved"] is False)
    check("is_favourite is false", climb["is_favourite"] is False)
    check("has route_hold_ids", climb["route_hold_ids"] is not None)

    # List (saved only — should be empty)
    r = client.get(f"/walls/{wall_id}/climbs", headers=HEADERS)
    check("list climbs returns 200", r.status_code == 200)
    check("no saved climbs yet", len(r.json()) == 0)

    # Save
    r = client.patch(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS, json={"is_saved": True})
    check("save returns 200", r.status_code == 200)
    check("is_saved is true", r.json()["is_saved"] is True)

    r = client.get(f"/walls/{wall_id}/climbs", headers=HEADERS)
    check("1 saved climb in list", len(r.json()) == 1)

    # Favourite implies saved
    client.patch(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS, json={"is_saved": False})
    r = client.patch(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS, json={"is_favourite": True})
    check("favourite auto-saves", r.json()["is_saved"] is True)
    check("is_favourite is true", r.json()["is_favourite"] is True)

    # Unsave clears favourite
    r = client.patch(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS, json={"is_saved": False})
    check("unsave clears favourite", r.json()["is_favourite"] is False)

    # Mark sent
    r = client.patch(f"/walls/{wall_id}/climbs/{climb_id}/sent", headers=HEADERS)
    check("mark sent returns 200", r.status_code == 200)
    check("date_sent is set", r.json()["date_sent"] is not None)

    # Get single
    r = client.get(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS)
    check("GET single climb", r.status_code == 200)

    # Delete
    r = client.delete(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS)
    check("DELETE climb returns 204", r.status_code == 204)

    r = client.get(f"/walls/{wall_id}/climbs/{climb_id}", headers=HEADERS)
    check("deleted climb returns 404", r.status_code == 404)


def test_delete_wall():
    print("\n[Delete Wall]")
    wid = simulate_ready_wall()
    r = client.delete(f"/walls/{wid}", headers=HEADERS)
    check("DELETE wall returns 204", r.status_code == 204)

    r = client.get(f"/walls/{wid}", headers=HEADERS)
    check("deleted wall returns 404", r.status_code == 404)


def test_input_validation():
    print("\n[Input Validation]")
    wid = simulate_ready_wall()

    r = client.post(f"/walls/{wid}/climbs", headers=HEADERS, json={"difficulty": "extreme", "style": "static"})
    check("invalid difficulty returns 400", r.status_code == 400)

    r = client.post(f"/walls/{wid}/climbs", headers=HEADERS, json={"difficulty": "easy", "style": "parkour"})
    check("invalid style returns 400", r.status_code == 400)

    r = client.get(f"/walls/{wid}/climbs/99999", headers=HEADERS)
    check("nonexistent climb returns 404", r.status_code == 404)


def test_auth_required():
    print("\n[Auth Required]")
    # Note: with mocked auth, missing header still succeeds (mock has default).
    # In production, real auth.get_current_user uses Header(...) which returns 422.
    # We verify the mock doesn't crash without a header.
    r = client.get("/walls")
    check("request without auth doesn't crash", r.status_code in (200, 422))


if __name__ == "__main__":
    print("=" * 60)
    print("SASQUATCH API TESTS")
    print("=" * 60)

    try:
        test_health()
        test_user_profile()
        wall_id = test_wall_lifecycle()
        test_error_before_ready(wall_id)
        test_process(wall_id)
        ready_wall_id = test_holds()
        test_climb_lifecycle(ready_wall_id)
        test_delete_wall()
        test_input_validation()
        test_auth_required()

        print("\n" + "=" * 60)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)
        sys.exit(1 if failed else 0)

    finally:
        if os.path.exists("test_sasquatch.db"):
            os.unlink("test_sasquatch.db")
