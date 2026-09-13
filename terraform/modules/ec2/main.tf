data "aws_ami" "amazon_linux_2023" {
  # Amazon Linux 2023 の最新 AMI を自動取得します。
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}

resource "aws_instance" "app" {
  # アプリケーションを実行する EC2 インスタンスです。
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.instance_type
  key_name      = var.key_name

  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [var.ec2_sg_id]
  iam_instance_profile        = var.iam_instance_profile_name
  user_data_replace_on_change = true

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-ec2"
  }

  user_data = <<-EOF
              #!/bin/bash
              # 起動時にスワップを作成し、小さなインスタンスでもメモリ不足を補います。
              fallocate -l 2G /swapfile
              chmod 600 /swapfile
              mkswap /swapfile
              swapon /swapfile
              echo '/swapfile swap swap defaults 0 0' >> /etc/fstab

              # Docker と Git など、アプリ起動に必要な基本ソフトをインストールします。
              dnf update -y
              dnf install -y docker git
              
              # Docker Compose V2 のインストール
              mkdir -p /usr/local/lib/docker/cli-plugins
              curl -SL https://github.com/docker/compose/releases/download/v2.24.1/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
              chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
              
              # Docker を起動し、再起動後も自動起動するようにします。
              systemctl start docker
              systemctl enable docker
              usermod -a -G docker ec2-user

              # アプリケーションのソースコードを取得します。
              mkdir -p /home/ec2-user/learning-app
              chown ec2-user:ec2-user /home/ec2-user/learning-app
              sudo -u ec2-user git clone https://github.com/rtiak-ops/learning-app.git /home/ec2-user/learning-app || (cd /home/ec2-user/learning-app && sudo -u ec2-user git pull)

              # DB 接続情報などを .env に書き出し、コンテナから読み込めるようにします。
              cat <<EOT > /home/ec2-user/learning-app/.env
              DATABASE_URL=postgresql+asyncpg://postgresMaster:${var.db_password}@${var.rds_endpoint}/todo_db
              POSTGRES_USER=postgresMaster
              POSTGRES_PASSWORD=${var.db_password}
              POSTGRES_DB=todo_db
              SECRET_KEY=${var.secret_key}
              ENV=${var.environment}
              DEBUG=false
              CORS_ORIGINS=http://${aws_eip.app.public_ip},http://localhost,http://localhost:5173
              VITE_API_BASE_URL=http://${aws_eip.app.public_ip}
              DOMAIN_NAME=${aws_eip.app.public_ip}
              GOOGLE_API_KEY=${var.google_api_key}
              EOT
              chown ec2-user:ec2-user /home/ec2-user/learning-app/.env

              # Docker イメージをビルドしてアプリケーションを起動します。
              cd /home/ec2-user/learning-app
              docker compose up -d --build
              
              # DB の準備が整うまで再試行し、スキーマを最新状態に更新します。
              for i in {1..12}; do
                docker compose exec -T backend alembic upgrade head && break
                sleep 5
              done
              EOF
}

resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}

resource "aws_eip_association" "eip_assoc" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}
