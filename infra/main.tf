terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "networking" {
  source = "./modules/networking"

  project_name = var.project_name
  aws_region   = var.aws_region
}

module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
}

module "iam" {
  source = "./modules/iam"

  project_name       = var.project_name
  aws_region         = var.aws_region
  bedrock_model_id   = var.bedrock_model_id
  dynamodb_table_arn = module.dynamodb.table_arn
}

module "alb" {
  source = "./modules/alb"

  project_name    = var.project_name
  vpc_id          = module.networking.vpc_id
  public_subnets  = module.networking.public_subnet_ids
  alb_sg_id       = module.networking.alb_security_group_id
  certificate_arn = var.certificate_arn
}

module "dynamodb" {
  source = "./modules/dynamodb"

  project_name = var.project_name
}

module "ecs" {
  source = "./modules/ecs"

  project_name       = var.project_name
  aws_region         = var.aws_region
  bedrock_model_id   = var.bedrock_model_id
  container_cpu      = var.container_cpu
  container_memory   = var.container_memory
  log_level          = var.log_level
  ecr_repository_url = module.ecr.repository_url
  private_subnets    = module.networking.private_subnet_ids
  ecs_sg_id          = module.networking.ecs_security_group_id
  target_group_arn   = module.alb.target_group_arn
  execution_role_arn = module.iam.execution_role_arn
  task_role_arn      = module.iam.task_role_arn
}

module "monitoring" {
  source = "./modules/monitoring"

  project_name = var.project_name
}
