# GitHub Actions から AWS に安全にアクセスするための OIDC プロバイダ情報を取得します。
# これにより、長くて秘密にしづらい AWS アクセスキーを使わずに、GitHub Actions から
# 一時的な認証情報を受け取り、必要な権限だけを使えるようにします。
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# GitHub Actions 用の IAM ロールです。
# このロールは GitHub の特定リポジトリのみから AssumeRole できるように制限し、
# S3 / CloudFront / EC2 / RDS などのデプロイや運用に必要な権限を持たせます。
resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
          }
        }
      }
    ]
  })
}

# GitHub Actions ロールに対して、CI/CD で実際に必要な権限だけを付与します。
# ここではデプロイ対象の S3/CloudFront の更新や、EC2/RDS の状態確認を行えるようにしています。
# 「広すぎる権限」を避けるため、基本は必要最小限のアクセスに絞る設計です。
resource "aws_iam_role_policy" "github_actions_policy" {
  name = "${var.project_name}-github-actions-policy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject",
          "cloudfront:CreateInvalidation",
          "cloudfront:ListDistributions",
          "cloudfront:GetDistribution",
          "ec2:DescribeInstances",
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "rds:DescribeDBInstances",
          "resourcegroupstaggingapi:GetResources"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# EC2 インスタンスが AWS Systems Manager (SSM) 経由で管理できるようにするロールです。
# 例: SSH ではなく SSM Session Manager を使って安全にインスタンスへ接続する場合に利用します。
resource "aws_iam_role" "ec2_ssm_role" {
  name = "${var.project_name}-ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# EC2 インスタンスに紐づけるポリシーをアタッチします。
# AmazonSSMManagedInstanceCore は SSM でインスタンスを管理するために必要な基本権限をまとめて持ちます。
resource "aws_iam_role_policy_attachment" "ssm_managed_core" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# EC2 インスタンスにこの IAM ロールを紐付けるためのインスタンスプロファイルです。
# EC2 側で profile を指定することで、SSM を使った運用が可能になります。
resource "aws_iam_instance_profile" "ec2_ssm_profile" {
  name = "${var.project_name}-ec2-ssm-profile"
  role = aws_iam_role.ec2_ssm_role.name
}
