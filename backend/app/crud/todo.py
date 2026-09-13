from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas


async def get_todos(db: AsyncSession, owner_id: int, project_id: int | None = None, q: str | None = None) -> list[models.Todo]:
    """
    Todoアイテムのリストを取得します。プロジェクトIDやキーワードでの絞り込みが可能です。

    Args:
        db (AsyncSession): データベースセッション
        owner_id (int): 実行ユーザーのID
        project_id (int | None): 特定のプロジェクトで絞り込む場合のプロジェクトID
        q (str | None): タイトルまたは説明文に含まれる検索キーワード

    Returns:
        list[models.Todo]: Todoモデルのリスト（表示順序 order の昇順でソート）
    """
    # 基本のクエリ（表示順でソート）
    stmt = select(models.Todo).order_by(models.Todo.order)
    # 個人タスク、所有プロジェクトのタスク、共同編集プロジェクトのタスクを返す。
    stmt = (
        stmt.outerjoin(models.Project, models.Todo.project_id == models.Project.id)
        .outerjoin(
            models.ProjectCollaborator,
            models.ProjectCollaborator.project_id == models.Project.id,
        )
        .where(
            or_(
                models.Todo.owner_id == owner_id,
                models.Project.owner_id == owner_id,
                models.ProjectCollaborator.user_id == owner_id,
            )
        )
        .distinct()
    )

    # プロジェクト指定がある場合
    if project_id:
        stmt = stmt.where(models.Todo.project_id == project_id)
    
    # キーワード検索（タイトルまたは説明文）
    if q:
        stmt = stmt.where(
            models.Todo.title.ilike(f"%{q}%") | models.Todo.description.ilike(f"%{q}%")
        )
        
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_todo(db: AsyncSession, todo: schemas.TodoCreate, owner_id: int) -> models.Todo:
    """
    新しいTodoアイテムを作成します。

    Args:
        db (AsyncSession): データベースセッション
        todo (schemas.TodoCreate): 作成するTodoの内容
        owner_id (int): オーナーとなるユーザーID

    Returns:
        models.Todo: 作成されたTodoモデル
    """
    new_todo = models.Todo(**todo.model_dump(), owner_id=owner_id) 
    db.add(new_todo)
    await db.commit()
    await db.refresh(new_todo)
    return new_todo

async def update_todo(db: AsyncSession, todo_id: int, todo: schemas.TodoUpdate) -> models.Todo | None:
    """
    指定されたIDのTodoアイテムを更新します。

    Args:
        db (AsyncSession): データベースセッション
        todo_id (int): 更新対象のTodo ID
        todo (schemas.TodoUpdate): 更新内容
        owner_id (int): 実行ユーザーのID（所有者チェック用）

    Returns:
        models.Todo | None: 更新後のTodoモデル、存在しない場合は None
    """
    result = await db.execute(select(models.Todo).where(models.Todo.id == todo_id))
    db_todo = result.scalar_one_or_none()
    
    if db_todo:
        # 送信された項目（unsetでないもの）のみをモデルに反映
        update_data = todo.model_dump(exclude_unset=True) 
        for key, value in update_data.items():
            setattr(db_todo, key, value)
            
        await db.commit()
        await db.refresh(db_todo)
        
    return db_todo

async def delete_todo(db: AsyncSession, todo_id: int) -> models.Todo | None:
    """
    指定されたIDのTodoアイテムを削除します。

    Args:
        db (AsyncSession): データベースセッション
        todo_id (int): 削除対象のTodo ID
        owner_id (int): 実行ユーザーのID（所有者チェック用）

    Returns:
        models.Todo | None: 削除されたTodoモデル、存在しない場合は None
    """
    result = await db.execute(select(models.Todo).where(models.Todo.id == todo_id))
    db_todo = result.scalar_one_or_none()
    
    if db_todo:
        await db.delete(db_todo)
        await db.commit()
        
    return db_todo

async def get_todo_by_id(db: AsyncSession, todo_id: int) -> models.Todo | None:
    """
    指定されたIDのTodoアイテムを1件取得します。

    Args:
        db (AsyncSession): データベースセッション
        todo_id (int): 取得対象のTodo ID
        owner_id (int): 実行ユーザーのID

    Returns:
        models.Todo | None: 見つかったTodoモデル、存在しない場合は None
    """
    result = await db.execute(
        select(models.Todo).where(models.Todo.id == todo_id)
    )
    return result.scalar_one_or_none()

async def reorder_todos(db: AsyncSession, todo_ids: list[int], owner_id: int):
    """
    ドラッグ&ドロップなどによる複数のTodoの表示順序を一括で更新します。

    Args:
        db (AsyncSession): データベースセッション
        todo_ids (list[int]): 新しい並び順に沿ったTodo IDのリスト
        owner_id (int): 実行ユーザーのID
    """
    # 指定されたIDのTodoを一括取得
    stmt = (
        select(models.Todo)
        .where(models.Todo.id.in_(todo_ids))
        .where(models.Todo.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    todos = {t.id: t for t in result.scalars().all()}
    
    # リストのインデックスを新しい order 値として設定
    for index, t_id in enumerate(todo_ids):
        if t_id in todos:
            todo = todos[t_id]
            if todo.order != index:
                todo.order = index
                db.add(todo)
    
    await db.commit()
