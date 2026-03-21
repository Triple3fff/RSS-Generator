from typing import Optional
from sqlmodel import Field, SQLModel


class AuthConfig(SQLModel, table=True):
    __tablename__ = "auth_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    password_hash: str
