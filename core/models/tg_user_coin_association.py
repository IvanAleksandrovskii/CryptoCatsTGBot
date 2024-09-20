from sqlalchemy import ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from .tg_user import TGUser
from .crypto_coin import Coin


class UserCoinAssociation(Base):
    __tablename__ = "user_coin_associations"

    user_id: Mapped[str] = mapped_column(ForeignKey("tg_users.id"), primary_key=True)
    coin_id: Mapped[str] = mapped_column(ForeignKey("coins.id"), primary_key=True)

    min_rate: Mapped[float] = mapped_column(Float, nullable=True)
    max_rate: Mapped[float] = mapped_column(Float, nullable=True)

    rate_percentage_growth: Mapped[float] = mapped_column(Float, nullable=True)
    rate_percentage_declines: Mapped[float] = mapped_column(Float, nullable=True)

    saved_rate_to_compare: Mapped[float] = mapped_column(Float, nullable=True)

    user: Mapped["TGUser"] = relationship(back_populates="coin_associations")
    coin: Mapped["Coin"] = relationship(back_populates="user_associations")

    def __repr__(self):
        return f"UserCoinAssociation(user_id={self.user_id}, coin_id={self.coin_id}, min_rate={self.min_rate}, max_rate={self.max_rate})"
