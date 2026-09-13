# 🌐 Modern AI-Powered ToDo - Frontend

このディレクトリには、Modern AI-Powered ToDo App のユーザーインターフェースが含まれています。  
React と TypeScript をベースに、高速で直感的な操作感を実現するモダンなフロントエンドスタックを採用しています。

---

## ✨ 主な特徴

- **AI連携 UI**: ボタン一つでタスクをAIが分解。結果をリアルタイムでリストに反映。
- **ドラッグ＆ドロップ**: `@hello-pangea/dnd` によるシームレスなタスク並び替え。
- **楽観的更新 (Optimistic Updates)**: `TanStack Query` により、API通信の完了を待たずにUIが即座に反応し、オフラインに近い軽快な操作感を提供。
- **完全レスポンシブ**: `Tailwind CSS` による、モバイル・デスクトップ両対応のデザイン。
- **リッチなフィードバック**: `react-hot-toast` による通知と、スケルトンローディングによるスムーズな画面遷移。

---

## 🛠️ 技術スタック

- **Core**: `React 19`, `TypeScript`
- **Build Tool**: `Vite`
- **State Management**: `TanStack Query (React Query) v5`
- **Styling**: `Tailwind CSS`, `Lucide React` (Icons)
- **Forms**: `React Hook Form`, `Zod`
- **Testing**: `Vitest`, `React Testing Library`

---

## 🚀 開発ガイド

### 1. セットアップ

```bash
npm install
```

### 2. 開発サーバーの起動

```bash
# .env の VITE_API_BASE_URL がバックエンドを向いていることを確認
npm run dev
```

### 3. ビルド

```bash
npm run build
```

### 4. テストの実行

```bash
# 単発実行
npm run test

# UIモードでの実行
npm run test:ui
```

---

## 📂 ディレクトリ構成

- `src/components`: 再利用可能な UI コンポーネント
- `src/hooks`: カスタムフック (データフェッチ、認証ロジック等)
- `src/api.ts`: API クライアント定義 (axios)
- `src/types`: TypeScript の型定義
- `src/App.tsx`: アプリケーションのエントリポイント・ルーティング

---

**Crafted with Interface Excellence by rtiak-ops**
