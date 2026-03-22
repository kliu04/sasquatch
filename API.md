# Sasquatch API Reference

## Base URL

```
http://<server-host>:8000
```

## Authentication

Every request (except `GET /health`) requires a Google OAuth2 ID token:

```
Authorization: Bearer <google_id_token>
```

**iOS with Google Sign-In:**
1. User signs in with `GIDSignIn`
2. Get token: `GIDSignIn.sharedInstance.currentUser?.idToken?.tokenString`
3. Refresh before each call: `try await GIDSignIn.sharedInstance.currentUser?.refreshTokensIfNeeded()`
4. Send as `Authorization: Bearer <token>`

The server verifies the token with Google, extracts the user ID (`sub` claim), and auto-creates a user on first sign-in. No registration endpoint needed.

The server's `GOOGLE_CLIENT_ID` in `database/auth.py` must match the iOS app's OAuth client ID. Currently set to `None` (accepts any valid Google token).

## Full Upload -> Detect -> Route Flow

### Step 1: Create wall (get signed upload URLs)
```
POST /walls
<- {"name": "My Gym Wall"}
-> 201
{
    "id": 1,
    "name": "My Gym Wall",
    "status": "pending_upload",
    "ply_upload_url": "https://storage.googleapis.com/...?X-Goog-Signature=...",
    "png_upload_url": "https://storage.googleapis.com/...?X-Goog-Signature=...",
    "created_at": "2026-03-21T..."
}
```

### Step 2: Upload files directly to GCS
```
PUT <ply_upload_url>
Content-Type: application/octet-stream
Body: <raw PLY file bytes>

PUT <png_upload_url>
Content-Type: image/png
Body: <raw PNG file bytes>
```
Direct-to-GCS uploads (no auth header needed, signature is in the URL). Use `URLSession` background upload for the ~116MB PLY file.

### Step 3: Trigger processing
```
POST /walls/1/process
-> 202 {"wall_id": 1, "status": "processing"}
```

### Step 4: Wait for processing

**Long polling (recommended):**
```
GET /walls/1?poll=true&timeout=30
```
Server holds connection up to 30s, returns when status becomes `ready` or `error`. Loop until ready:
```swift
func waitForReady(wallId: Int) async throws -> Wall {
    while true {
        let wall = try await api.getWall(wallId, poll: true, timeout: 30)
        if wall.status == .ready || wall.status == .error { return wall }
    }
}
```

**Simple polling:** `GET /walls/1` every 3-5 seconds, check `status` field.

### Step 5: View detected holds
```
GET /walls/1/holds
-> 200
{
    "wall_id": 1,
    "holds": [
        {"id": 0, "position": {"x": 1.23, "y": 3.45, "z": 0.12}, "bbox": {"x1": 100, "y1": 200, "x2": 150, "y2": 260}, "confidence": 0.95, "depth": 0.032},
        ...
    ]
}
```
Returns 409 if wall status is not `ready`.

Wall detail also includes image URLs: `wall_img_url`, `holds_image_url`.

### Step 6: Generate climbing routes
```
POST /walls/1/climbs
<- {
    "difficulty": "medium",    // easy | medium | hard
    "style": "static",        // static | dynamic
    "wingspan": 1.75,         // optional, defaults to user.wingspan or 1.8
    "top_k": 3                // optional, defaults to 3
}
-> 201
[
    {
        "id": 1,
        "wall_id": 1,
        "difficulty": "medium",
        "classification": "static",
        "route_hold_ids": [3, 12, 7, 22, 31, 45],
        "is_saved": false,
        "is_favourite": false,
        "date_sent": null,
        "climb_img_url": "https://storage.googleapis.com/.../climbs/1.png",
        "created_at": "2026-03-21T..."
    },
    ...
]
```
Blocks (sub-second), generates `top_k` routes. All start with `is_saved: false`.

### Step 7: Save routes the user wants
```
PATCH /walls/1/climbs/1
<- {"is_saved": true}
-> 200 (updated climb)
```
`is_favourite: true` auto-sets `is_saved: true`. `is_saved: false` clears `is_favourite`.

## All Endpoints

### Health
```
GET /health -> {"status": "ok"}
```

### User Profile
```
GET  /users/me                              -> UserResponse
PATCH /users/me <- {username?, wingspan?}    -> UserResponse
```

### Walls
```
POST   /walls <- {name}                     -> 201 WallCreateResponse (with signed URLs)
POST   /walls/{id}/process                  -> 202 {wall_id, status}
GET    /walls                               -> [WallSummary]
GET    /walls/{id}                          -> WallDetail
GET    /walls/{id}?poll=true&timeout=30     -> WallDetail (long-polls)
DELETE /walls/{id}                          -> 204
```

### Holds
```
GET /walls/{id}/holds                       -> HoldsResponse (409 if not ready)
```

### Climbs
```
POST   /walls/{id}/climbs <- {difficulty, style, wingspan?, top_k?}  -> 201 [ClimbResponse]
GET    /walls/{id}/climbs                   -> [ClimbResponse] (saved only)
GET    /walls/{id}/climbs/{climb_id}        -> ClimbResponse
PATCH  /walls/{id}/climbs/{climb_id} <- {is_saved?, is_favourite?}   -> ClimbResponse
PATCH  /walls/{id}/climbs/{climb_id}/sent   -> ClimbResponse (sets date_sent=now)
DELETE /walls/{id}/climbs/{climb_id}        -> 204
```

## Wall Status Values

| Status | Meaning |
|--------|---------|
| `pending_upload` | Created, waiting for PLY/PNG upload to GCS |
| `processing` | Hold detection running |
| `ready` | Holds detected, routes can be generated |
| `error` | Failed, check `error_message` field |

## Error Codes

| Code | When |
|------|------|
| 400 | Invalid difficulty/style value |
| 401 | Missing or invalid Bearer token |
| 404 | Wall/climb not found or not owned by user |
| 409 | Wrong state (climbs before ready, re-process, etc.) |
| 422 | Missing required fields |

## Response Shapes

### UserResponse
```json
{"id": 1, "username": "Randy", "wingspan": 1.75}
```

### WallSummary
```json
{"id": 1, "name": "...", "status": "ready", "hold_count": 47, "wall_img_url": "https://...", "created_at": "..."}
```

### WallDetail
```json
{
    "id": 1, "name": "My Gym Wall", "status": "ready",
    "wall_img_url": "https://...", "wall_ply_url": "https://...",
    "holds_image_url": "https://...", "hold_count": 47,
    "error_message": null, "created_at": "2026-03-21T..."
}
```

### ClimbResponse
```json
{
    "id": 1, "wall_id": 1, "difficulty": "medium", "classification": "static",
    "route_hold_ids": [3, 12, 7, 22, 31, 45],
    "is_saved": false, "is_favourite": false, "date_sent": null,
    "climb_img_url": "https://...", "created_at": "2026-03-21T..."
}
```
