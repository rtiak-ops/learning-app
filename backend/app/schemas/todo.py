from __future__ import annotations

from datetime import datetime

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class TodoStatus(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"


class TodoPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TodoBase(BaseModel):
    """
    To Doアイテムが持つ基本的な属性を定義する。
    """
    title: str 
    description: str | None = None
    completed: bool = False
    project_id: int | None = None
    status: TodoStatus = TodoStatus.TODO
    priority: TodoPriority = TodoPriority.MEDIUM
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """
        タイトルが適切な条件を満たしているかチェックする。
        """
        if not v.strip():
            raise ValueError("Title cannot be empty")
        
        if len(v) > 100:
            raise ValueError("Title must be 100 characters or less")
        
        return v.strip()

class TodoCreate(TodoBase):
    """
    新しいTo Doアイテムを作成するためのスキーマ。
    """
    pass

class TodoUpdate(BaseModel): 
    """
    既存のTo Doアイテムを更新するためのスキーマ。
    """
    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    project_id: int | None = None
    status: TodoStatus | None = None
    priority: TodoPriority | None = None
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return TodoBase.validate_title(v)

class TodoOut(TodoBase):
    """
    データベースから取得したTo Doアイテムの情報をクライアントに返すためのスキーマ。
    """
    id: int
    created_at: datetime
    updated_at: datetime
    owner_id: int | None = None
    order: int = 0
                
    model_config = ConfigDict(from_attributes=True)

class TodoReorder(BaseModel):
    """
    To Doアイテムの表示順序を変更するためのスキーマ。
    """
    todo_ids: list[int]

    @field_validator("todo_ids")
    @classmethod
    def validate_unique_ids(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError("todo_ids must not contain duplicates")
        return v
