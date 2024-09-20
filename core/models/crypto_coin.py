from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .tg_user_coin_association import UserCoinAssociation


class Coin(Base):
    name: Mapped[str] = mapped_column(String, nullable=True)  # TODO: for now this field is unused

    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    coin_id_for_price_getter: Mapped[String] = mapped_column(String, nullable=True)

    user_associations: Mapped[list["UserCoinAssociation"]] = relationship(back_populates="coin")

    def __repr__(self):
        return f"Coin(code='{self.code}', id={self.id})"

    def __str__(self):
        return f"{self.code}"
