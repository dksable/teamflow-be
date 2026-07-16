from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email.lower())
        return self.db.scalar(statement)
