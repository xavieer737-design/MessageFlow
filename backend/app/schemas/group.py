from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class GroupCreate(GroupBase):
    pass


class GroupUpdate(GroupBase):
    pass


class GroupBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    description: str | None
    created_at: datetime
    contact_count: int = 0


class GroupDetailOut(GroupOut):
    contact_ids: list[int] = Field(default_factory=list)


class GroupAddContactsRequest(BaseModel):
    contact_ids: list[int] = Field(default_factory=list)


class GroupRemoveContactsRequest(BaseModel):
    contact_ids: list[int] = Field(default_factory=list)
