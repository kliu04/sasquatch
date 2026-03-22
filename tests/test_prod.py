"""Production API smoke tests against the live Cloud Run deployment.

Tests the full API flow against the real server, real DB, and real GCS.
Requires a valid Google OAuth2 ID token.

Run with:
  .venv/bin/python tests/test_prod.py
  .venv/bin/python tests/test_prod.py --token <google_id_token>
  .venv/bin/python tests/test_prod.py --url https://your-service.run.app
"""
import argparse
import json
import sys
import time

import requests

BASE_URL = "https://sasquatch-379138604067.us-central1.run.app"
TOKEN = None  # Set via --token or skips auth-required tests

passed = 0
failed = 0
created_wall_ids = []
created_climb_ids = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        msg = f"  FAIL: {name}"
        if detail:
            msg += f" ({detail})"
        print(msg)


def headers():
    h = {}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def get(path, **kwargs):
    return requests.get(f"{BASE_URL}{path}", headers=headers(), timeout=30, **kwargs)


def post(path, json_body=None, **kwargs):
    return requests.post(f"{BASE_URL}{path}", headers=headers(), json=json_body, timeout=30, **kwargs)


def patch(path, json_body=None, **kwargs):
    return requests.patch(f"{BASE_URL}{path}", headers=headers(), json=json_body, timeout=30, **kwargs)


def delete(path, **kwargs):
    return requests.delete(f"{BASE_URL}{path}", headers=headers(), timeout=30, **kwargs)


# ── Tests ──


def test_health():
    print("\n[Health]")
    r = requests.get(f"{BASE_URL}/health", timeout=10)
    check("returns 200", r.status_code == 200, f"got {r.status_code}")
    check("body is ok", r.json() == {"status": "ok"}, f"got {r.json()}")


def test_no_auth():
    print("\n[Auth Required]")
    r = requests.get(f"{BASE_URL}/walls", timeout=10)
    check("no auth returns 422", r.status_code == 422, f"got {r.status_code}")


def test_user_profile():
    print("\n[User Profile]")
    r = get("/users/me")
    check("GET /users/me returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:100]}")
    if r.status_code != 200:
        return

    data = r.json()
    check("has id", "id" in data)
    check("has username", "username" in data)
    check("has wingspan", "wingspan" in data)

    # Update wingspan
    r = patch("/users/me", {"wingspan": 1.77})
    check("PATCH wingspan returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check("wingspan updated", r.json()["wingspan"] == 1.77)


def test_wall_create():
    print("\n[Wall Create]")
    r = post("/walls", {"name": "Prod Test Wall"})
    check("POST /walls returns 201", r.status_code == 201, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code != 201:
        return None

    data = r.json()
    check("has id", "id" in data)
    check("status is pending_upload", data["status"] == "pending_upload")
    check("has ply_upload_url", "ply_upload_url" in data and data["ply_upload_url"].startswith("https://"))
    check("has png_upload_url", "png_upload_url" in data and data["png_upload_url"].startswith("https://"))

    wall_id = data["id"]
    created_wall_ids.append(wall_id)

    # Verify signed URLs are valid by checking they're real GCS URLs
    check("ply URL is GCS signed", "X-Goog-Signature" in data.get("ply_upload_url", ""))
    check("png URL is GCS signed", "X-Goog-Signature" in data.get("png_upload_url", ""))

    return wall_id


def test_wall_list():
    print("\n[Wall List]")
    r = get("/walls")
    check("GET /walls returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("returns array", isinstance(data, list))
        check("has walls", len(data) >= 1)
        if data:
            w = data[0]
            check("wall has id", "id" in w)
            check("wall has name", "name" in w)
            check("wall has status", "status" in w)


def test_wall_get(wall_id):
    print("\n[Wall Get]")
    r = get(f"/walls/{wall_id}")
    check("GET /walls/{id} returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("correct id", data["id"] == wall_id)
        check("has status", "status" in data)
        check("has created_at", "created_at" in data)


def test_wall_not_found():
    print("\n[Wall Not Found]")
    r = get("/walls/999999")
    check("nonexistent wall returns 404", r.status_code == 404, f"got {r.status_code}")


def test_holds_before_ready(wall_id):
    print("\n[Holds Before Ready]")
    r = get(f"/walls/{wall_id}/holds")
    check("holds before ready returns 409", r.status_code == 409, f"got {r.status_code}")


def test_climbs_before_ready(wall_id):
    print("\n[Climbs Before Ready]")
    r = post(f"/walls/{wall_id}/climbs", {"difficulty": "medium", "style": "static"})
    check("climbs before ready returns 409", r.status_code == 409, f"got {r.status_code}")


def test_process_wall(wall_id):
    print("\n[Process Wall]")
    # This will trigger processing, which will fail since we didn't actually upload files
    # But the endpoint should accept the request (202)
    r = post(f"/walls/{wall_id}/process")
    check("process returns 202", r.status_code == 202, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 202:
        check("status is processing", r.json()["status"] == "processing")

    # Re-process should fail
    r = post(f"/walls/{wall_id}/process")
    check("re-process returns 409", r.status_code == 409, f"got {r.status_code}")


def test_input_validation():
    print("\n[Input Validation]")
    # Create a wall to test against
    r = post("/walls", {"name": "Validation Test"})
    if r.status_code != 201:
        print("  SKIP: couldn't create wall")
        return
    wid = r.json()["id"]
    created_wall_ids.append(wid)

    r = get(f"/walls/{wid}/climbs/999999")
    check("nonexistent climb returns 404", r.status_code == 404, f"got {r.status_code}")


def test_delete_wall(wall_id):
    print("\n[Delete Wall]")
    r = delete(f"/walls/{wall_id}")
    check("DELETE returns 204", r.status_code == 204, f"got {r.status_code}")

    r = get(f"/walls/{wall_id}")
    check("deleted wall returns 404", r.status_code == 404, f"got {r.status_code}")


def cleanup():
    """Delete any walls created during testing."""
    print("\n[Cleanup]")
    for wid in created_wall_ids:
        try:
            delete(f"/walls/{wid}")
        except Exception:
            pass
    print(f"  Cleaned up {len(created_wall_ids)} test walls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sasquatch production API tests")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of the API")
    parser.add_argument("--token", help="Google OAuth2 ID token for auth")
    args = parser.parse_args()

    BASE_URL = args.url.rstrip("/")
    TOKEN = args.token

    print("=" * 60)
    print(f"SASQUATCH PROD API TESTS")
    print(f"URL: {BASE_URL}")
    print(f"Auth: {'token provided' if TOKEN else 'NO TOKEN (auth tests will be limited)'}")
    print("=" * 60)

    try:
        # Always works (no auth needed)
        test_health()
        test_no_auth()

        if TOKEN:
            test_user_profile()
            wall_id = test_wall_create()
            test_wall_list()
            if wall_id:
                test_wall_get(wall_id)
                test_holds_before_ready(wall_id)
                test_climbs_before_ready(wall_id)
                test_process_wall(wall_id)
            test_wall_not_found()
            test_input_validation()

            # Clean up all created walls
            cleanup()
        else:
            print("\n  SKIP: auth-required tests (no --token provided)")
            print("  Get a token: use Google OAuth2 playground or your iOS app")

        print("\n" + "=" * 60)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)
        sys.exit(1 if failed else 0)

    except Exception as e:
        print(f"\nFATAL: {e}")
        cleanup()
        sys.exit(1)
