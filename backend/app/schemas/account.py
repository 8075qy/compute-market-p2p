from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    balance_points: int
    reserve_points: int
    frozen_points: int
    total_earned: int
    total_spent: int
    reserve_contribution: int = Field(0, description="储备贡献率（万分比，0-10000）")
    pool_total_points: int = Field(0, description="公共池总储备分")
    pool_contributors: int = Field(0, description="公共池贡献人数")

    model_config = ConfigDict(from_attributes=True)
