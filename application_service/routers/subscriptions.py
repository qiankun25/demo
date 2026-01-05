from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db
from models import User, UserSubscription, SubscriptionType
from schemas import SubscriptionCreate, SubscriptionResponse


def convert_subscription_to_response(subscription: UserSubscription) -> SubscriptionResponse:
    """将数据库订阅对象转换为响应对象，处理字符串到枚举的转换"""
    # 将字符串类型的subscription_type转换为枚举
    if isinstance(subscription.subscription_type, str):
        type_str = subscription.subscription_type
        try:
            # 首先尝试直接按值匹配（小写：journal, scholar, keyword）
            subscription_type = SubscriptionType(type_str.lower())
        except ValueError:
            try:
                # 如果小写不匹配，尝试按成员名匹配（大写：JOURNAL, SCHOLAR, KEYWORD）
                subscription_type = SubscriptionType[type_str.upper()]
            except (KeyError, ValueError):
                # 如果都不匹配，尝试直接按值（保持原样）
                subscription_type = SubscriptionType(type_str)
    else:
        subscription_type = subscription.subscription_type
    
    return SubscriptionResponse(
        id=subscription.id,
        user_id=subscription.user_id,
        subscription_type=subscription_type,
        subscription_value=subscription.subscription_value
    )

router = APIRouter(prefix="/api/subscriptions", tags=["订阅"])


def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="用户ID")
) -> int:
    """获取当前用户ID（从请求头）"""
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供用户ID，请在请求头中添加 X-User-ID"
        )
    try:
        return int(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户ID格式错误，必须是整数"
        )


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户对象"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建订阅"""
    # 验证订阅值长度
    if len(subscription_data.subscription_value) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订阅值长度不能超过100个字符"
        )
    
    if len(subscription_data.subscription_value.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订阅值不能为空"
        )
    
    # 检查是否已存在相同的订阅（利用唯一约束）
    existing = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.subscription_type == subscription_data.subscription_type.value,
        UserSubscription.subscription_value == subscription_data.subscription_value.strip()
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该订阅已存在"
        )
    
    # 创建新订阅（将枚举转换为字符串值）
    new_subscription = UserSubscription(
        user_id=current_user.id,
        subscription_type=subscription_data.subscription_type.value,
        subscription_value=subscription_data.subscription_value.strip()
    )
    
    db.add(new_subscription)
    db.commit()
    db.refresh(new_subscription)
    
    return convert_subscription_to_response(new_subscription)


@router.get("", response_model=List[SubscriptionResponse], operation_id="get_all_subscriptions")
async def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有订阅信息"""
    subscriptions = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id
    ).all()
    
    return [convert_subscription_to_response(sub) for sub in subscriptions]


@router.get("/{subscription_id}", response_model=SubscriptionResponse, operation_id="get_subscription_by_id")
async def get_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定订阅详情"""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.id == subscription_id,
        UserSubscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订阅不存在"
        )
    
    return convert_subscription_to_response(subscription)


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新订阅"""
    # 验证订阅值长度
    if len(subscription_data.subscription_value) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订阅值长度不能超过100个字符"
        )
    
    if len(subscription_data.subscription_value.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订阅值不能为空"
        )
    
    # 查找订阅
    subscription = db.query(UserSubscription).filter(
        UserSubscription.id == subscription_id,
        UserSubscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订阅不存在"
        )
    
    # 检查是否与其他订阅冲突（排除自己）
    existing = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.subscription_type == subscription_data.subscription_type.value,
        UserSubscription.subscription_value == subscription_data.subscription_value.strip(),
        UserSubscription.id != subscription_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该订阅已存在"
        )
    
    # 更新订阅
    subscription.subscription_type = subscription_data.subscription_type.value
    subscription.subscription_value = subscription_data.subscription_value.strip()
    
    db.commit()
    db.refresh(subscription)
    
    return convert_subscription_to_response(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除订阅"""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.id == subscription_id,
        UserSubscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订阅不存在"
        )
    
    db.delete(subscription)
    db.commit()
    
    return None

