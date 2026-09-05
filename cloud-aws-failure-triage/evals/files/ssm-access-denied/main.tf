data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

resource "aws_ecs_task_definition" "web" {
  family                   = "web-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  task_role_arn            = aws_iam_role.web_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = file("${path.module}/containers/web.json")
}
