from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas


async def get_projects(db: AsyncSession, user_id: int) -> list[models.Project]:
    """
    ユーザーがアクセス可能なすべてのプロジェクトを取得します。
    所属組織のプロジェクト、または自分がオーナー/共同編集者であるプロジェクトが対象です。

    Args:
        db (AsyncSession): データベースセッション
        user_id (int): 実行ユーザーのID

    Returns:
        list[models.Project]: プロジェクトモデルのリスト
    """
    # プロジェクトは、オーナーまたは明示的に追加された共同編集者だけが閲覧できる。
    # 組織所属だけで全プロジェクトを公開しないことで、Viewer / Editor 権限を実効化する。
    collab_stmt = select(models.ProjectCollaborator.project_id).where(
        models.ProjectCollaborator.user_id == user_id
    )
    stmt = select(models.Project).where(
        or_(
            models.Project.owner_id == user_id,
            models.Project.id.in_(collab_stmt),
        )
    )

    # 共同編集者情報も含めて読み込み、作成日時の降順でソート
    stmt = stmt.options(
        selectinload(models.Project.collaborators)
        .selectinload(models.ProjectCollaborator.user)
    ).order_by(models.Project.created_at.desc())

    result = await db.execute(stmt)
    return result.scalars().all()

async def get_project_by_id(db: AsyncSession, project_id: int, user_id: int) -> models.Project | None:
    """
    IDを指定して特定のプロジェクトを取得します。アクセス権限（オーナーまたは共同編集者）を確認します。

    Args:
        db (AsyncSession): データベースセッション
        project_id (int): 取得するプロジェクトのID
        user_id (int): 実行ユーザーのID

    Returns:
        models.Project | None: アクセス可能な場合はプロジェクトモデル、それ以外は None
    """
    stmt = (
        select(models.Project)
        .where(models.Project.id == project_id)
        .options(selectinload(models.Project.collaborators))
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        return None
    
    # オーナーチェック
    if project.owner_id == user_id:
        return project
    
    # 共同編集者チェック
    is_collab = any(c.user_id == user_id for c in project.collaborators)
    if is_collab:
        return project
        
    return None


async def get_project_collaboration(
    db: AsyncSession, project_id: int, user_id: int
) -> models.ProjectCollaborator | None:
    """指定ユーザーのプロジェクト共同編集者レコードを取得する。"""
    result = await db.execute(
        select(models.ProjectCollaborator).where(
            models.ProjectCollaborator.project_id == project_id,
            models.ProjectCollaborator.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()

async def is_project_editor(db: AsyncSession, project_id: int, user_id: int) -> bool:
    """
    ユーザーがプロジェクトに対して編集権限（owner または permission='editor'）を持っているか判定します。

    Args:
        db (AsyncSession): データベースセッション
        project_id (int): プロジェクトID
        user_id (int): 判定するユーザーID

    Returns:
        bool: 編集権限があれば True
    """
    stmt = select(models.Project).where(models.Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        return False
    
    # オーナーは常に編集可能
    if project.owner_id == user_id:
        return True
        
    collaboration = await get_project_collaboration(db, project_id, user_id)
    return collaboration is not None and collaboration.permission == "editor"

async def create_project(db: AsyncSession, project: schemas.ProjectCreate, owner_id: int) -> models.Project:
    """
    新しいプロジェクトを作成します。

    Args:
        db (AsyncSession): データベースセッション
        project (schemas.ProjectCreate): 作成するプロジェクトの内容
        owner_id (int): オーナーとなるユーザーID

    Returns:
        models.Project: 作成されたプロジェクトモデル
    """
    # オーナーの組織情報を取得して自動設定
    user_result = await db.execute(select(models.User).where(models.User.id == owner_id))
    user = user_result.scalar_one_or_none()
    org_id = user.organization_id if user else None

    # プロジェクトの保存
    db_project = models.Project(**project.model_dump(), owner_id=owner_id, organization_id=org_id)
    db.add(db_project)
    await db.commit()
    
    # 最新の状態を読み込んで返す
    stmt = select(models.Project).where(models.Project.id == db_project.id).options(
        selectinload(models.Project.collaborators)
    )
    result = await db.execute(stmt)
    db_project = result.scalar()
    return db_project

async def update_project(db: AsyncSession, project_id: int, project: schemas.ProjectUpdate, user_id: int) -> models.Project | None:
    """
    プロジェクト情報を更新します（編集権限が必要）。

    Args:
        db (AsyncSession): データベースセッション
        project_id (int): 更新対象のプロジェクトID
        project (schemas.ProjectUpdate): 更新内容
        user_id (int): 実行ユーザーのID

    Returns:
        models.Project | None: 更新後のプロジェクトモデル、権限なしや存在しない場合は None
    """
    # 編集権限チェック
    if not await is_project_editor(db, project_id, user_id):
        return None
        
    stmt = select(models.Project).where(models.Project.id == project_id)
    result = await db.execute(stmt)
    db_project = result.scalar_one_or_none()
    
    if not db_project:
        return None
    
    # 送信された項目のみを更新
    update_data = project.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)
    
    await db.commit()
    await db.refresh(db_project)
    return db_project

async def delete_project(db: AsyncSession, project_id: int, user_id: int) -> models.Project | None:
    """
    プロジェクトを削除します。オーナーのみ実行可能です。

    Args:
        db (AsyncSession): データベースセッション
        project_id (int): 削除対象のプロジェクトID
        user_id (int): 実行ユーザーのID

    Returns:
        models.Project | None: 削除されたプロジェクト、削除に失敗した場合は None
    """
    # オーナー一致を確認しつつ取得
    stmt = select(models.Project).where(models.Project.id == project_id, models.Project.owner_id == user_id)
    result = await db.execute(stmt)
    db_project = result.scalar_one_or_none()
    
    if db_project:
        await db.delete(db_project)
        await db.commit()
    return db_project

async def get_project_summaries(db: AsyncSession, user_id: int):
    """
    ユーザーが関わっている各プロジェクトのタスク進捗状況を含む要約リストを取得します。

    Args:
        db (AsyncSession): データベースセッション
        user_id (int): 実行ユーザーのID

    Returns:
        list[dict]: プロジェクト要約情報のリスト（タスク数、完了数、ロール等を含む）
    """
    projects = await get_projects(db, user_id)
    
    summaries = []
    for p in projects:
        # プロジェクト内の全タスク数と完了済みタスク数を集計
        todo_stmt = select(func.count(models.Todo.id)).where(models.Todo.project_id == p.id)
        completed_stmt = select(func.count(models.Todo.id)).where(models.Todo.project_id == p.id, models.Todo.completed)
        
        todo_count = (await db.execute(todo_stmt)).scalar() or 0
        completed_count = (await db.execute(completed_stmt)).scalar() or 0
        
        # 実行ユーザーの役割（オーナーか共同編集者か）
        role = "owner" if p.owner_id == user_id else "collaborator"

        # 共同編集者リストの整形
        collaborators_out = []
        for c in p.collaborators:
            collaborators_out.append({
                "id": c.id,
                "user_id": c.user_id,
                "permission": c.permission,
                "user_email": c.user.email if c.user else None
            })

        summary = {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "owner_id": p.owner_id,
            "todo_count": todo_count,
            "completed_count": completed_count,
            "role": role,
            "collaborators": collaborators_out
        }
        summaries.append(summary)
        
    return summaries

async def add_collaborator(db: AsyncSession, project_id: int, collaborator: schemas.CollaboratorCreate) -> models.ProjectCollaborator:
    """
    プロジェクトに新しい共同編集者を追加します。

    Args:
        db (AsyncSession): データベースセッション
        project_id (int): 対象プロジェクトのID
        collaborator (schemas.CollaboratorCreate): 追加するユーザーと権限の情報

    Returns:
        models.ProjectCollaborator: 作成された共同編集者レコード
    """
    project_result = await db.execute(select(models.Project).where(models.Project.id == project_id))
    project = project_result.scalar_one_or_none()
    user_result = await db.execute(select(models.User).where(models.User.id == collaborator.user_id))
    user = user_result.scalar_one_or_none()
    if project is None or user is None:
        raise ValueError("Project or user not found")
    if project.organization_id != user.organization_id:
        raise ValueError("Users must belong to the same organization")
    if await get_project_collaboration(db, project_id, collaborator.user_id):
        raise ValueError("User is already a collaborator")

    db_collab = models.ProjectCollaborator(
        project_id=project_id,
        user_id=collaborator.user_id,
        permission=collaborator.permission
    )
    db.add(db_collab)
    await db.commit()
    await db.refresh(db_collab)
    return db_collab

async def remove_collaborator(db: AsyncSession, project_id: int, user_id: int):
    """
    プロジェクトから指定したユーザーの共同編集権限を削除します。

    Args:
        db (AsyncSession): データベースセッション
        project_id (int): 対象プロジェクトのID
        user_id (int): 削除するユーザーのID
    """
    stmt = delete(models.ProjectCollaborator).where(
        models.ProjectCollaborator.project_id == project_id,
        models.ProjectCollaborator.user_id == user_id
    )
    await db.execute(stmt)
    await db.commit()
