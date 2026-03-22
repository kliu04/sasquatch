from fastapi import Depends, Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from database.db import get_db
from database.schema import User

GOOGLE_CLIENT_ID = None  # set via env or replace with your client ID


def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")

    token = authorization.removeprefix("Bearer ")

    # Dev bypass: "Bearer dev" skips Google verification
    if token == "dev":
        google_id = "dev-user"
        decoded = {"sub": google_id, "name": "Dev User"}
    else:
        try:
            decoded = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=GOOGLE_CLIENT_ID,
            )
        except ValueError as e:
            raise HTTPException(401, f"Invalid token: {e}")

        google_id = decoded["sub"]

    user = db.query(User).filter(User.google_id == google_id).first()
    if user is None:
        # Auto-create user on first sign-in
        user = User(
            google_id=google_id,
            username="Sasquatch",
            wingspan=200.66,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
