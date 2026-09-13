resource "aws_iam_role" "scheduler_lambda" {
  # Lambda が EC2/RDS の起動・停止と CloudWatch Logs 出力を行うためのロールです。
  name = "${var.project_name}-scheduler-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_lambda_policy" {
  name = "${var.project_name}-scheduler-lambda-policy"
  role = aws_iam_role.scheduler_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "rds:DescribeDBInstances",
          "rds:StartDBInstance",
          "rds:StopDBInstance"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "stop_instances" {
  # 指定時刻に EC2 と RDS を停止して、不要な稼働コストを抑えます。
  filename      = var.lambda_stop_zip
  function_name = "${var.project_name}-stop-instances"
  role          = aws_iam_role.scheduler_lambda.arn
  handler       = "index.handler"
  runtime       = "python3.13"
  timeout       = 60

  # source_code_hash calculation moved to caller or handled here if possible
  # For now, simplistic
  source_code_hash = filebase64sha256(var.lambda_stop_zip)

  environment {
    variables = {
      EC2_INSTANCE_ID = var.ec2_instance_id
      RDS_INSTANCE_ID = var.rds_instance_id
    }
  }
}

resource "aws_lambda_function" "start_instances" {
  # 指定時刻に EC2 と RDS を起動します。ルールは初期状態で無効です。
  filename      = var.lambda_start_zip
  function_name = "${var.project_name}-start-instances"
  role          = aws_iam_role.scheduler_lambda.arn
  handler       = "index.handler"
  runtime       = "python3.13"
  timeout       = 60

  source_code_hash = filebase64sha256(var.lambda_start_zip)

  environment {
    variables = {
      EC2_INSTANCE_ID = var.ec2_instance_id
      RDS_INSTANCE_ID = var.rds_instance_id
    }
  }
}

resource "aws_cloudwatch_event_rule" "stop_daily" {
  # EventBridge から停止用 Lambda を定期実行します（cron は UTC）。
  name                = "${var.project_name}-stop-daily"
  schedule_expression = "cron(0 9,15 * * ? *)" 
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "stop_daily" {
  rule      = aws_cloudwatch_event_rule.stop_daily.name
  target_id = "StopInstances"
  arn       = aws_lambda_function.stop_instances.arn
}

resource "aws_lambda_permission" "allow_eventbridge_stop_daily" {
  statement_id  = "AllowExecutionFromEventBridgeDailyStop"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stop_instances.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stop_daily.arn
}

resource "aws_cloudwatch_event_rule" "start_daily" {
  # EventBridge から起動用 Lambda を定期実行するルールです。
  name                = "${var.project_name}-start-daily"
  schedule_expression = "cron(0 3 * * ? *)"
  state               = "DISABLED" # Keep disabled by default unless requested
}

resource "aws_cloudwatch_event_target" "start_daily" {
  rule      = aws_cloudwatch_event_rule.start_daily.name
  target_id = "StartInstances"
  arn       = aws_lambda_function.start_instances.arn
}

resource "aws_lambda_permission" "allow_eventbridge_start_daily" {
  statement_id  = "AllowExecutionFromEventBridgeDailyStart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_instances.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.start_daily.arn
}
