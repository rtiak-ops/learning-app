from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .. import dependencies, models
from ..database import get_db

router = APIRouter(prefix="/monitor", tags=["Monitoring"])

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(dependencies.admin_required),
):
    """
    システムの稼働状況（ヘルスチェック）を確認します。
    データベースへの接続テストと基本情報の取得を行います。
    """
    start_time = time.time()
    try:
        # データベースに対してシンプルなクエリを実行し、接続を確認
        await db.execute(text("SELECT 1"))
        db_status = "operational"
    except Exception as exc:
        # 接続エラーの詳細は外部レスポンスに含めない。
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable") from exc
    
    # データベースの応答時間を計測
    db_latency = time.time() - start_time

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "database": {
            "status": db_status,
            "latency_sec": round(db_latency, 4)
        },
        "version": "1.1.0"
    }

@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(dependencies.admin_required)
):
    """
    システム全体の統計情報を取得します（管理者権限が必要）。
    管理者本人が所属している組織に関連するデータ件数を集計します。
    """
    from sqlalchemy import func, select

    from ..models import AuditLog, Project, Todo, User

    # 各テーブルのレコード件数を取得するための基本クエリ
    user_stmt = select(func.count(User.id))
    project_stmt = select(func.count(Project.id))
    todo_stmt = select(func.count(Todo.id))
    audit_stmt = select(func.count(AuditLog.id))

    # 管理者が特定の組織に所属している場合、その組織のデータのみに絞り込む
    if current_user.organization_id:
        user_stmt = user_stmt.where(User.organization_id == current_user.organization_id)
        project_stmt = project_stmt.where(Project.organization_id == current_user.organization_id)
        # Todo（タスク）はユーザーを介して組織と紐付いているためJOINして判定
        todo_stmt = todo_stmt.join(User, Todo.owner_id == User.id).where(User.organization_id == current_user.organization_id)
        audit_stmt = audit_stmt.where(AuditLog.organization_id == current_user.organization_id)

    # クエリを実行して結果を取得
    user_count = (await db.execute(user_stmt)).scalar()
    project_count = (await db.execute(project_stmt)).scalar()
    todo_count = (await db.execute(todo_stmt)).scalar()
    audit_count = (await db.execute(audit_stmt)).scalar()

    return {
        "counts": {
            "users": user_count,
            "projects": project_count,
            "tasks": todo_count,
            "audit_logs": audit_count
        }
    }
