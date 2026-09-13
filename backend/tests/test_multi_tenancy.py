import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_organization_and_association(client: AsyncClient):
    """
    正常系: 組織を作成し、ユーザーがその組織に自動的に紐付けられることを確認
    """
    email = "creator_unique@test.com"
    password = "password123"
    await client.post("/auth/register", json={"email": email, "password": password})
    login_res = await client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    org_payload = {"name": "Unique Corp 1", "corporate_id": "9999999999991"}
    response = await client.post("/organizations/", json=org_payload, headers=headers)
    assert response.status_code == 200
    
    me_res = await client.get("/organizations/me", headers=headers)
    assert me_res.status_code == 200
    # 作成した組織が自分に反映されていること
    assert me_res.json()["name"] == "Unique Corp 1"

@pytest.mark.asyncio
async def test_multi_tenancy_isolation(client: AsyncClient):
    """
    重要: 組織間のデータ隔離（マルチテナント）を確認
    """
    # 組織A
    email_a = "user_a_isolation_unique@test.com"
    await client.post("/auth/register", json={"email": email_a, "password": "password123"})
    login_a = await client.post("/auth/login", json={"email": email_a, "password": "password123"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    await client.post("/organizations/", json={"name": "Org A Unique"}, headers=headers_a)
    await client.post("/projects/", json={"name": "Project A"}, headers=headers_a)

    # 組織B
    email_b = "user_b_isolation_unique@test.com"
    await client.post("/auth/register", json={"email": email_b, "password": "password123"})
    login_b = await client.post("/auth/login", json={"email": email_b, "password": "password123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    await client.post("/organizations/", json={"name": "Org B Unique"}, headers=headers_b)
    await client.post("/projects/", json={"name": "Project B"}, headers=headers_b)

    # 組織Aのユーザーは、組織Aのプロジェクトのみが見え、Bは見えないこと
    res_a = await client.get("/projects/", headers=headers_a)
    assert res_a.status_code == 200
    projects_a = res_a.json()
    assert any(p["name"] == "Project A" for p in projects_a)
    assert not any(p["name"] == "Project B" for p in projects_a)

    # 組織Bのユーザーは、組織Bのプロジェクトのみが見え、Aは見えないこと
    res_b = await client.get("/projects/", headers=headers_b)
    assert res_b.status_code == 200
    projects_b = res_b.json()
    assert any(p["name"] == "Project B" for p in projects_b)
    assert not any(p["name"] == "Project A" for p in projects_b)

@pytest.mark.asyncio
async def test_duplicate_organization_prevention(client: AsyncClient):
    """
    異常系: 同名組織の重複登録が防止されることを確認
    """
    email1 = "u1_dup_final@test.com"
    await client.post("/auth/register", json={"email": email1, "password": "password123"})
    l1 = await client.post("/auth/login", json={"email": email1, "password": "password123"})
    h1 = {"Authorization": f"Bearer {l1.json()['access_token']}"}
    await client.post("/organizations/", json={"name": "Duplicate Target Org"}, headers=h1)

    email2 = "u2_dup_final@test.com"
    await client.post("/auth/register", json={"email": email2, "password": "password123"})
    l2 = await client.post("/auth/login", json={"email": email2, "password": "password123"})
    h2 = {"Authorization": f"Bearer {l2.json()['access_token']}"}
    
    # すでに登録済みの名称で作成を試みる
    response = await client.post("/organizations/", json={"name": "Duplicate Target Org"}, headers=h2)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_project_editor_can_manage_shared_tasks_but_viewer_cannot(client: AsyncClient):
    """共同編集者の権限がプロジェクト内のタスク操作へ一貫して適用されること。"""
    async def register_and_login(email: str):
        await client.post("/auth/register", json={"email": email, "password": "password123"})
        response = await client.post("/auth/login", json={"email": email, "password": "password123"})
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    owner_headers = await register_and_login("owner_permissions@test.com")
    editor_headers = await register_and_login("editor_permissions@test.com")
    viewer_headers = await register_and_login("viewer_permissions@test.com")

    await client.post("/organizations/", json={"name": "Permissions Org"}, headers=owner_headers)
    for email in ("editor_permissions@test.com", "viewer_permissions@test.com"):
        response = await client.post("/admin/users/assign", json={"email": email}, headers=owner_headers)
        assert response.status_code == 200

    project_response = await client.post("/projects/", json={"name": "Shared project"}, headers=owner_headers)
    project_id = project_response.json()["id"]
    users = await client.get("/admin/users", headers=owner_headers)
    ids = {user["email"]: user["id"] for user in users.json()}
    for email, permission in (("editor_permissions@test.com", "editor"), ("viewer_permissions@test.com", "viewer")):
        response = await client.post(
            f"/projects/{project_id}/collaborators",
            json={"user_id": ids[email], "permission": permission},
            headers=owner_headers,
        )
        assert response.status_code == 200

    create_response = await client.post(
        "/todos/", json={"title": "Editor task", "project_id": project_id}, headers=editor_headers
    )
    assert create_response.status_code == 201
    todo_id = create_response.json()["id"]

    owner_todos = await client.get("/todos/", headers=owner_headers)
    assert any(todo["id"] == todo_id for todo in owner_todos.json())

    viewer_create = await client.post(
        "/todos/", json={"title": "Blocked task", "project_id": project_id}, headers=viewer_headers
    )
    assert viewer_create.status_code == 403
    viewer_update = await client.patch(f"/todos/{todo_id}", json={"title": "Blocked update"}, headers=viewer_headers)
    assert viewer_update.status_code == 403


@pytest.mark.asyncio
async def test_todo_and_collaborator_inputs_are_validated(client: AsyncClient):
    headers = await client.post("/auth/register", json={"email": "validation@test.com", "password": "password123"})
    assert headers.status_code == 201
    login = await client.post("/auth/login", json={"email": "validation@test.com", "password": "password123"})
    auth_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    invalid_todo = await client.post("/todos/", json={"title": "x", "priority": "NOW"}, headers=auth_headers)
    assert invalid_todo.status_code == 422
    invalid_project = await client.post("/projects/", json={"name": "   "}, headers=auth_headers)
    assert invalid_project.status_code == 422
