from pydantic import BaseModel, EmailStr
from typing import Optional, List
from models import SubscriptionType


# 用户注册请求
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str


# 用户登录请求
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


# 用户响应（不包含敏感信息）
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    
    class Config:
        from_attributes = True


# 订阅相关 Schema
class SubscriptionCreate(BaseModel):
    subscription_type: SubscriptionType
    subscription_value: str


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    subscription_type: SubscriptionType
    subscription_value: str
    
    class Config:
        from_attributes = True

