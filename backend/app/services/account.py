import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Account


class AccountService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account(self, user_id: uuid.UUID) -> Account:
        stmt = select(Account).where(Account.user_id == user_id)
        account = (await self.session.execute(stmt)).scalar_one_or_none()
        if not account:
            raise NotFoundError("账户不存在")
        return account

    async def get_account_overview(self, user_id: uuid.UUID) -> dict:
        account = await self.get_account(user_id)

        # 公共池总量与贡献人数（用于储备贡献率可见）
        pool_total = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Account.reserve_points), 0))
                )
            ).scalar_one()
            or 0
        )
        contributors = int(
            (
                await self.session.execute(
                    select(func.count(Account.id)).where(Account.reserve_points > 0)
                )
            ).scalar_one()
            or 0
        )
        contribution = (
            account.reserve_points * 10000 // pool_total if pool_total > 0 else 0
        )

        return {
            "balance_points": account.balance_points,
            "reserve_points": account.reserve_points,
            "frozen_points": account.frozen_points,
            "total_earned": account.total_earned,
            "total_spent": account.total_spent,
            "reserve_contribution": contribution,
            "pool_total_points": pool_total,
            "pool_contributors": contributors,
        }
