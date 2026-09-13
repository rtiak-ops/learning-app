# ==============================================
# ステージ1: ビルド用（重いツールを使って料理を作る）
# ==============================================
FROM node:23-slim AS build-stage

# コンテナ内の作業ディレクトリを指定
WORKDIR /app

# ライブラリの定義ファイルを先にコピー（キャッシュを効かせてビルドを速くするため）
COPY package*.json ./

# 必要なライブラリ（node_modules）をインストール
RUN npm ci

# プロジェクトの全ファイルをコピー
COPY . .

# ReactやVueなどのソースコードを、ブラウザで読み込める静的ファイル（dist）に変換
# ※この工程が終われば、Node.js自体はもう不要になります
RUN npm run build


# ==============================================
# ステージ2: 実行用（できた料理を軽量なサーバーで配る）
# ==============================================
FROM nginx:alpine

# 1. ビルドステージで生成された「成果物（dist内のファイル）」だけを取り出す
# これにより、最終的なイメージサイズを劇的に軽量化できます
COPY --from=build-stage /app/dist /usr/share/nginx/html

# 2. 環境変数の設定（バックエンドの接続先など）
# コンテナ起動時に上書き可能ですが、何も指定しない場合のデフォルト値を決めておきます
ENV BACKEND_URL=http://backend:8000

# 3. Nginxの設定テンプレートをコピー
# /etc/nginx/templates/ 内に .template ファイルを置くと、
# 起動時に環境変数が適用された設定ファイルが自動生成されます（Nginx公式の仕組み）
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# 4. セキュリティ対策: 非rootユーザーでの実行
# Nginxをnginxユーザーで実行（alpineイメージには既にnginxユーザーが存在）
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

USER nginx

# コンテナが80番ポートで待機することを明示
EXPOSE 80

# ヘルスチェック設定
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

# Nginxをフォアグラウンドで実行（コンテナが終了しないようにするため）
CMD ["nginx", "-g", "daemon off;"]
