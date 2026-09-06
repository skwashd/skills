data "aws_iam_policy_document" "web_task_assume" {
  statement {
    sid     = "ECSTasksAssume"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "web_task" {
  name               = "web-app-task"
  assume_role_policy = data.aws_iam_policy_document.web_task_assume.json
}

data "aws_iam_policy_document" "web_task" {
  statement {
    sid = "ReadAppParameters"
    actions = [
      "ssm:GetParameter",
    ]
    resources = [
      "arn:aws:ssm:eu-west-1:123456789012:parameter/apps/web/prod/db_host",
      "arn:aws:ssm:eu-west-1:123456789012:parameter/apps/web/prod/db_name",
    ]
  }

  statement {
    sid = "WriteAppLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:eu-west-1:123456789012:log-group:/apps/web/prod:*",
    ]
  }
}

resource "aws_iam_role_policy" "web_task" {
  name   = "web-app-task"
  role   = aws_iam_role.web_task.id
  policy = data.aws_iam_policy_document.web_task.json
}
