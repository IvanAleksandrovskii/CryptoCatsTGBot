from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Coin(Base):
    name: Mapped[str] = mapped_column(String, nullable=True)  # TODO: for now this field is unused

    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    coin_id_for_price_getter: Mapped[String] = mapped_column(String, nullable=True)

    # chains: Mapped[List["Chain"]] = relationship(
    #     "Chain",
    #     secondary=coin_chain,
    #     back_populates="coins",
    #     lazy="selectin",
    #     cascade="save-update, merge",
    # )
    # pools: Mapped[List["CoinPoolOffer"]] = relationship(
    #     "CoinPoolOffer",
    #     back_populates="coin",
    #     lazy="noload",
    #     cascade="save-update, merge, delete, delete-orphan",
    # )
    # prices: Mapped[List["CoinPrice"]] = relationship(
    #     "CoinPrice",
    #     back_populates="coin",
    #     lazy="noload",
    #     cascade="all, delete-orphan",
    #     order_by="desc(CoinPrice.created_at)",
    # )

    def __repr__(self):
        return f"Coin(code='{self.code}', id={self.id})"

    def __str__(self):
        return f"{self.code}"
