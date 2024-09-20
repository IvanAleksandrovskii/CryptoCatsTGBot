from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class TGUser(Base):
    __tablename__ = "tg_users"

    username: Mapped[str] = mapped_column(String, nullable=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)

    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __str__(self):
        return f"TGUser(id={self.id}, username={self.username}, chat_id={self.chat_id})"

    def __repr__(self) -> str:
        return self.__str__()
