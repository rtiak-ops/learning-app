"""
ToDoアイテムのCRUD操作を行うAPIルーター

このモジュールは、ToDoアイテムに関する以下の操作を提供します:
- 全ToDoアイテムの取得（ログインユーザーのもののみ）
- 新しいToDoアイテムの作成
- 既存ToDoアイテムの更新（部分更新対応）
- ToDoアイテムの削除
- ToDoアイテムの並び替え

全てのエンドポイントは認証が必要で、ログインユーザーのToDoのみを操作できます。
"""

from __future__ import annotations  # Python 3.10+: 型ヒントの前方参照を簡潔に

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, dependencies, models, schemas
from ..database import get_db

# ===========================
# ルーター設定
# ===========================
# APIRouterのインスタンスを作成
# prefix="/todos"で全てのルーティングが/todosから始まる
# tags=["Todos"]でAPIドキュメント（Swagger UI/Redoc）でのグループ名を指定
router = APIRouter(prefix="/todos", tags=["Todos"])


async def require_todo_editor(
    db: AsyncSession, todo: models.Todo, current_user: models.User
) -> None:
    """個人タスクは所有者のみ、プロジェクトタスクは Editor のみ変更できる。"""
    if todo.project_id is None:
        if todo.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return
    if not await crud.is_project_editor(db, todo.project_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor permission is required")


# ===========================
# ToDoアイテムの読み取り（全件取得）
# ===========================
@router.get(
    "/",
    response_model=list[schemas.TodoOut],  # レスポンスのPydanticモデルを指定（リスト型であることに注意）
    status_code=status.HTTP_200_OK  # 成功時のHTTPステータスコードを明示的に指定（200 OK）
)
async def read_todos(
    q: str | None = None, # 検索クエリ
    db: AsyncSession = Depends(get_db),  # DBセッションを依存性注入で取得
    current_user: models.User = Depends(dependencies.get_current_user),  # 認証済みユーザー情報を取得
) -> list[schemas.TodoOut]:
    """
    ログインユーザーの全ToDoアイテムを取得します（検索対応）。
    """
    # crudモジュールの非同期関数を呼び出し、データベースからToDoリストを取得
    # owner_idを指定することで、ログインユーザーのToDoのみを取得
    todos = await crud.get_todos(db, owner_id=current_user.id, q=q)
    return todos  # 取得したToDoリストを返す


# ===========================
# ToDoアイテムの作成
# ===========================
@router.post(
    "/",
    response_model=schemas.TodoOut,  # レスポンスのPydanticモデルを指定（作成されたアイテム）
    status_code=status.HTTP_201_CREATED  # 作成成功時のHTTPステータスコードを明示的に指定（201 Created）
)
async def create_todo(
    todo: schemas.TodoCreate,  # リクエストボディをschemas.TodoCreateモデルで検証
    db: AsyncSession = Depends(get_db),  # DBセッションを依存性注入で取得
    current_user: models.User = Depends(dependencies.get_current_user),  # 認証済みユーザー情報を取得
) -> schemas.TodoOut:
    """
    新しいToDoアイテムを作成します。
    
    【処理の流れ】
    1. リクエストボディからToDoの情報（タイトル、説明など）を受け取る
    2. 現在のログインユーザーをToDoの所有者として設定
    3. データベースに新しいToDoアイテムを保存
    4. 作成されたToDoアイテムの情報を返却
    
    【パラメータ】
    - todo: 作成するToDoの情報（title, description, completedなど）
    - db: データベースセッション（自動注入）
    - current_user: 認証済みユーザー情報（自動注入）
    
    【戻り値】
    - 作成されたToDoアイテムの完全な情報（IDや作成日時を含む）
    
    【エラー】
    - 401 Unauthorized: 認証トークンが無効または期限切れの場合
    - 422 Unprocessable Entity: リクエストボディのバリデーションエラー
    """
    if todo.project_id is not None and not await crud.is_project_editor(db, todo.project_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor permission is required")

    # crudモジュールの非同期関数を呼び出し、ToDoアイテムを作成
    # owner_idを指定することで、ログインユーザーのToDoとして作成
    new_todo = await crud.create_todo(db, todo=todo, owner_id=current_user.id)
    
    # 監査ログを記録
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="CREATE", 
        resource_type="TODO", 
        resource_id=new_todo.id,
        details={"title": new_todo.title},
        organization_id=current_user.organization_id
    )
    
    return new_todo  # 作成されたToDoアイテムを返す


# ===========================
# ToDoアイテムの更新（部分更新/全体更新）
# ===========================
@router.patch(
    "/{todo_id}",
    response_model=schemas.TodoOut,  # レスポンスのPydanticモデルを指定（更新されたアイテム）
    status_code=status.HTTP_200_OK  # 成功時のHTTPステータスコードを明示的に指定（200 OK）
)
async def update_todo(
    todo_id: int,  # URLパスから更新対象のToDoのIDを取得
    todo: schemas.TodoUpdate,  # リクエストボディをschemas.TodoUpdateモデルで検証
    db: AsyncSession = Depends(get_db),  # DBセッションを依存性注入で取得
    current_user: models.User = Depends(dependencies.get_current_user),  # 認証済みユーザー情報を取得
) -> schemas.TodoOut:
    """
    指定されたIDのToDoアイテムを更新します（部分更新対応）。
    
    【処理の流れ】
    1. URLパスから更新対象のToDoのIDを取得
    2. リクエストボディから更新する項目を受け取る（全項目必須ではない）
    3. 指定されたIDのToDoが存在し、かつログインユーザーの所有であることを確認
    4. 指定された項目のみをデータベースで更新
    5. 更新後のToDoアイテムの情報を返却
    
    【パラメータ】
    - todo_id: 更新対象のToDoのID（URLパスパラメータ）
    - todo: 更新する項目（title, description, completedなど、指定された項目のみ更新）
    - db: データベースセッション（自動注入）
    - current_user: 認証済みユーザー情報（自動注入）
    
    【戻り値】
    - 更新されたToDoアイテムの完全な情報
    
    【エラー】
    - 401 Unauthorized: 認証トークンが無効または期限切れの場合
    - 404 Not Found: 指定されたIDのToDoが存在しない、または他のユーザーの所有の場合
    - 422 Unprocessable Entity: リクエストボディのバリデーションエラー
    """
    # crudモジュールの非同期関数を呼び出し、ToDoアイテムを更新
    # owner_idを指定することで、ログインユーザーのToDoのみを更新可能にする
    existing = await crud.get_todo_by_id(db, todo_id=todo_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Todo with id {todo_id} not found")
    await require_todo_editor(db, existing, current_user)

    # 移動先プロジェクトにも編集権限が必要。
    if todo.project_id is not None and todo.project_id != existing.project_id:
        if not await crud.is_project_editor(db, todo.project_id, current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor permission is required for destination project")

    updated = await crud.update_todo(db, todo_id=todo_id, todo=todo)
    
    # 更新対象が見つからなかった場合（存在しないIDまたは他のユーザーの所有）
    if updated is None:  # Noneチェックのほうがより明示的で安全
        # 404 Not Foundエラーを発生させ、クライアントに通知
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,  # 404 Not Found
            detail=f"Todo with id {todo_id} not found"  # 詳細なエラーメッセージ
        )
    
    # 監査ログを記録
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="UPDATE", 
        resource_type="TODO", 
        resource_id=updated.id,
        details=todo.model_dump(exclude_unset=True),
        organization_id=current_user.organization_id
    )

    return updated  # 更新されたToDoアイテムを返す


# ===========================
# ToDoアイテムの削除
# ===========================
@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_200_OK,  # 成功時のHTTPステータスコードを明示的に指定（200 OK）
    # 削除成功時はレスポンスボディとしてJSONオブジェクトを返すためresponse_modelは不要
)
async def delete_todo(
    todo_id: int,  # URLパスから削除対象のToDoのIDを取得
    db: AsyncSession = Depends(get_db),  # DBセッションを依存性注入で取得
    current_user: models.User = Depends(dependencies.get_current_user),  # 認証済みユーザー情報を取得
) -> dict:  # 辞書型（JSONオブジェクト）を返すことを示唆
    """
    指定されたIDのToDoアイテムを削除します。
    
    【処理の流れ】
    1. URLパスから削除対象のToDoのIDを取得
    2. 指定されたIDのToDoが存在し、かつログインユーザーの所有であることを確認
    3. データベースから該当のToDoアイテムを削除
    4. 削除成功メッセージを返却
    
    【パラメータ】
    - todo_id: 削除対象のToDoのID（URLパスパラメータ）
    - db: データベースセッション（自動注入）
    - current_user: 認証済みユーザー情報（自動注入）
    
    【戻り値】
    - 削除成功メッセージと削除されたToDoのIDを含むJSONオブジェクト
    
    【エラー】
    - 401 Unauthorized: 認証トークンが無効または期限切れの場合
    - 404 Not Found: 指定されたIDのToDoが存在しない、または他のユーザーの所有の場合
    """
    # crudモジュールの非同期関数を呼び出し、ToDoアイテムを削除
    # owner_idを指定することで、ログインユーザーのToDoのみを削除可能にする
    existing = await crud.get_todo_by_id(db, todo_id=todo_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Todo with id {todo_id} not found",
        )
    await require_todo_editor(db, existing, current_user)
    deleted = await crud.delete_todo(db, todo_id=todo_id)
    
    # 削除対象が見つからなかった場合（存在しないIDまたは他のユーザーの所有）
    if not deleted:  # bool値のFalseが返された場合（削除対象が見つからない/削除に失敗）
        # 404 Not Foundエラーを発生させ、クライアントに通知
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,  # 404 Not Found
            detail=f"Todo with id {todo_id} not found"  # 詳細なエラーメッセージ
        )
    
    # 監査ログを記録
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="DELETE", 
        resource_type="TODO", 
        resource_id=todo_id,
        organization_id=current_user.organization_id
    )

    # 削除成功メッセージを返す
    return {"message": "Deleted successfully", "todo_id": todo_id}


# ===========================
# ToDoアイテムの並び替え
# ===========================
@router.post("/reorder", status_code=status.HTTP_200_OK)
async def reorder_todos(
    payload: schemas.TodoReorder,  # リクエストボディから新しい並び順（IDのリスト）を取得
    db: AsyncSession = Depends(get_db),  # DBセッションを依存性注入で取得
    current_user: schemas.UserOut = Depends(dependencies.get_current_user),  # 認証済みユーザー情報を取得
):
    """
    ToDoアイテムの並び順を更新します。
    
    【処理の流れ】
    1. リクエストボディから新しい並び順（ToDoのIDリスト）を受け取る
    2. 各ToDoのorder_indexを新しい順序に従って更新
    3. ログインユーザーのToDoのみを対象とする
    4. 更新成功メッセージを返却
    
    【パラメータ】
    - payload: 新しい並び順を表すToDoのIDリスト（todo_ids）
    - db: データベースセッション（自動注入）
    - current_user: 認証済みユーザー情報（自動注入）
    
    【戻り値】
    - 並び替え成功メッセージを含むJSONオブジェクト
    
    【エラー】
    - 401 Unauthorized: 認証トークンが無効または期限切れの場合
    - 422 Unprocessable Entity: リクエストボディのバリデーションエラー
    
    【使用例】
    ドラッグ&ドロップでToDoの順序を変更した際に、フロントエンドから
    新しい順序のIDリストを送信してデータベースに反映させます。
    """
    # crudモジュールの非同期関数を呼び出し、ToDoの並び順を更新
    # owner_idを指定することで、ログインユーザーのToDoのみを並び替え可能にする
    # 並び替えは所有タスクだけを対象にし、他ユーザーのタスクを変更させない。
    await crud.reorder_todos(db, todo_ids=payload.todo_ids, owner_id=current_user.id)
    return {"message": "Order updated"}
