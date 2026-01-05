from sqlalchemy import Column, BigInteger, String, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import enum


class SubscriptionType(str, enum.Enum):
    """订阅类型枚举"""
    JOURNAL = "journal"
    SCHOLAR = "scholar"
    KEYWORD = "keyword"


class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # 关系：用户的订阅
    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (
        UniqueConstraint('user_id', 'subscription_type', 'subscription_value', name='unique_subscription'),
    )
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_type = Column(String(20), nullable=False)
    subscription_value = Column(String(100), nullable=False)
    
    # 关系：所属用户
    user = relationship("User", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<UserSubscription(id={self.id}, user_id={self.user_id}, type={self.subscription_type}, value={self.subscription_value})>"

