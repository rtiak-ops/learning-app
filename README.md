# Learning App

React / FastAPI / PostgreSQL で構成された、チーム向けのAIタスク管理アプリです。プロジェクトとタスクを整理し、優先度・期限・権限・監査ログを一つの画面で管理できます。抽象的なタスクは Gemini または OpenAI API を使って実行可能なサブタスクへ分解できます。

[![Backend CI](https://github.com/rtiak-ops/learning-app/actions/workflows/ci-backend.yml/badge.svg)](https://github.com/rtiak-ops/learning-app/actions/workflows/ci-backend.yml)
[![Frontend CI](https://github.com/rtiak-ops/learning-app/actions/workflows/ci-frontend.yml/badge.svg)](https://github.com/rtiak-ops/learning-app/actions/workflows/ci-frontend.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 主な機能

- タスクの作成・編集・削除、期限・優先度・ステータス管理
- ドラッグ＆ドロップによるタスクの並び替え
- プロジェクト横断の検索とダッシュボード
- Gemini 優先、OpenAI フォールバックのAIタスク分解
- 組織単位のマルチテナント設計
- Admin / User のロールと、Project 単位の Viewer / Editor 権限
- 監査ログ、管理者向けヘルス・パフォーマンス情報
- JWT認証、レート制限、CORS、CIでのテスト・セキュリティスキャン

## 画面

<p align="center">
  <img src="docs/images/dashBoard.png" alt="期限・優先度を横断して確認できるダッシュボード" width="49%">
  <img src="docs/images/project.png" alt="権限付きでタスクを管理するプロジェクト画面" width="49%">
</p>

- **ダッシュボード**: プロジェクトをまたいでタスクの状況、期限、優先度を確認
- **プロジェクト**: タスクと共同編集者をプロジェクト単位で管理

## 技術スタック

| 領域 | 採用技術 |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2 (Async), Pydantic v2 |
| Database | PostgreSQL 17, Alembic |
| AI | Google Gemini API / OpenAI API |
| Infrastructure | Docker Compose, AWS, Terraform |
| Quality | pytest, Vitest, React Testing Library, Ruff, GitHub Actions, Trivy |

## アーキテクチャ

```mermaid
flowchart LR
    User[利用者] --> Browser[ブラウザ]
    Browser --> Frontend[React / Vite\nNginx]
    Frontend -->|REST API / JWT| Backend[FastAPI]
    Backend --> DB[(PostgreSQL)]
    Backend -.->|優先| Gemini[Google Gemini API]
    Backend -.->|フォールバック| OpenAI[OpenAI API]
```

本番構成では、フロントエンドを S3 / CloudFront、バックエンドを EC2 上のDocker、データベースを RDS PostgreSQL に配置する想定です。Terraformの詳細は [`terraform/`](terraform/) を参照してください。

### 利用フロー

```mermaid
sequenceDiagram
    actor User as 利用者
    participant Web as Webアプリ
    participant API as FastAPI
    participant DB as PostgreSQL
    participant AI as Gemini / OpenAI

    User->>Web: 新規登録・ログイン
    Web->>API: 認証情報を送信
    API->>DB: ユーザーを照合
    DB-->>API: ユーザー情報
    API-->>Web: JWTを返却
    User->>Web: プロジェクト・タスクを操作
    Web->>API: JWT付きAPIリクエスト
    API->>DB: 権限を確認して保存・取得
    opt AIタスク分解
        API->>AI: タスクをサブタスクへ分解
        AI-->>API: サブタスク候補
        API-->>Web: 結果を返却
    end
```

## 必要条件

- Docker Desktop（Docker Compose v2）
- Git
- 個別起動する場合: Node.js、npm、Python 3.13
- AI分解を使う場合: `GOOGLE_API_KEY` または `OPENAI_API_KEY`

## クイックスタート（Docker）

```bash
git clone https://github.com/rtiak-ops/learning-app.git
cd learning-app
cp .env.example .env
```

`.env` を環境に合わせて編集します。最低限、データベースの3項目と `SECRET_KEY` を設定してください。AI機能を使わない場合、AI APIキーは空でも起動できます。

ローカルで起動する場合は、`.env.example` 内の外部IPをローカル向けの値に置き換えてください。

```dotenv
CORS_ORIGINS=http://localhost,http://localhost:5173
VITE_API_BASE_URL=http://localhost:8000
DOMAIN_NAME=localhost
```

`docker-compose.yml` はホストの `80`、`443`、`8000` ポートを使用します。起動前に、これらを使用するWebサーバーやコンテナが停止していることを確認してください。Compose構成はHTTPで動作し、HTTPS化にはドメインと証明書を用意したうえでNginx設定を変更します。

```bash
docker compose up --build
```

起動後は次のURLを開きます。

| URL | 用途 |
| --- | --- |
| [http://localhost](http://localhost) | Webアプリ |
| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI |
| [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc |

停止するには `Ctrl+C`、バックグラウンドのコンテナを停止するには次を実行します。

```bash
docker compose down
```

データベースのボリュームも削除する場合は、対象を確認したうえで `docker compose down -v` を実行してください。

### 初回利用

1. [http://localhost](http://localhost) を開き、**新規登録**から名前・メールアドレス・パスワードを登録します。
2. 登録したアカウントでログインします。最初に登録したユーザーには Admin ロールが自動的に付与されます。
3. 必要に応じてサイドバーから組織を作成し、プロジェクトとタスクを追加します。

## 個別起動（開発用）

### Backend

PostgreSQLを起動した状態で、別のターミナルから実行します。

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

APIは `http://localhost:8000` で起動します。テストは次のコマンドです。

```bash
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

フロントエンドのAPI接続先は `.env` の `VITE_API_BASE_URL` で指定します。通常のローカル開発では `http://localhost:8000` を設定してください。

```bash
npm run build       # 本番ビルド
npm run lint        # ESLint
npm run test        # Vitest
npm run test:coverage
```

## 環境変数

設定項目の一覧と例は [`.env.example`](.env.example) にあります。秘密情報をコミットしないでください。

| 変数 | 用途 |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQLの接続情報 |
| `DATABASE_URL` | FastAPIからDBへ接続するURL |
| `SECRET_KEY` | JWT署名用の秘密鍵 |
| `GOOGLE_API_KEY` | Geminiによるタスク分解（任意） |
| `OPENAI_API_KEY` | OpenAIによるタスク分解（任意） |
| `CORS_ORIGINS` | 許可するフロントエンドのオリジン |
| `VITE_API_BASE_URL` | フロントエンドが接続するAPIのURL |

本番環境では、強度の高い秘密鍵・パスワードを使い、`DEBUG=false` としてください。

> `.env.example` に含まれるIPアドレスは設定例です。公開環境では実際のドメインへ、ローカル環境では `localhost` へ必ず置き換えてください。

## ディレクトリ構成

```text
.
├── backend/          # FastAPI、SQLAlchemyモデル、Alembic、pytest
├── frontend/         # React / TypeScript / Vite
├── terraform/        # AWSインフラの定義
├── docs/              # スクリーンショット等
├── memo/              # 設計・コードリーディング資料
├── docker-compose.yml
└── .env.example
```

## データと権限

主要なデータは `organizations`、`users`、`projects`、`todos`、`project_collaborators`、`audit_logs` で構成されます。組織で利用者を分離し、プロジェクトはオーナーまたは明示的に追加された共同編集者のみが利用できます。

```mermaid
erDiagram
    ORGANIZATION ||--o{ USER : "has members"
    ORGANIZATION ||--o{ PROJECT : "owns"
    USER ||--o{ PROJECT : "owns"
    PROJECT ||--o{ TODO : "contains"
    USER ||--o{ TODO : "creates"
    USER ||--o{ PROJECT_COLLABORATOR : "is assigned"
    PROJECT ||--o{ PROJECT_COLLABORATOR : "grants access"
    USER ||--o{ AUDIT_LOG : "performs"
    ORGANIZATION ||--o{ AUDIT_LOG : "scopes"

    ORGANIZATION {
        int id PK
        string name
    }
    USER {
        int id PK
        string email
        string role
    }
    PROJECT {
        int id PK
        string name
        int owner_id FK
    }
    TODO {
        int id PK
        string title
        string status
        string priority
    }
    PROJECT_COLLABORATOR {
        int project_id FK
        int user_id FK
        string permission
    }
    AUDIT_LOG {
        int id PK
        string action
    }
```

### 権限の考え方

```mermaid
flowchart TD
    Request[APIリクエスト] --> Auth{JWTは有効か?}
    Auth -->|いいえ| Unauthorized[401 Unauthorized]
    Auth -->|はい| Scope{対象は?}
    Scope -->|個人タスク| Owner{作成者本人か?}
    Scope -->|プロジェクト| Access{オーナーまたは共同編集者か?}
    Owner -->|はい| Allow[操作を許可]
    Owner -->|いいえ| Forbidden[403 Forbidden]
    Access -->|いいえ| Forbidden
    Access -->|Viewer| Read[閲覧のみ許可]
    Access -->|Editor / Owner| Allow
```

- **Admin / User**: 組織レベルのロール
- **Viewer / Editor**: プロジェクト単位の操作権限
- **Todo status**: `TODO` / `IN_PROGRESS` / `REVIEW` / `DONE`
- **Todo priority**: `LOW` / `MEDIUM` / `HIGH` / `URGENT`

## AWSへのデプロイ

本番デプロイはTerraformとGitHub Actionsを利用します。AWSアカウント、認証情報、DNS・証明書などの環境依存設定が必要です。`apply` はAWSリソースを作成・変更するため、必ず `plan` の内容を確認してから実行してください。

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

デプロイ前に、ワークフロー（[`.github/workflows/`](.github/workflows/)）が要求するGitHub Secretsを確認してください。特に `SECRET_KEY`、DBパスワード、AWS認証情報、AI APIキーはリポジトリへ直接記載しないでください。環境固有のTerraform変数もリポジトリに含めず、安全な方法で管理してください。

## ドキュメント

- [認証フロー](memo/AUTH_FLOW.md)
- [コードリーディングガイド](memo/CODE_READING_GUIDE.md)
- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)
- [OpenAPI定義](openapi.json)

## ライセンス

[MIT License](LICENSE)
