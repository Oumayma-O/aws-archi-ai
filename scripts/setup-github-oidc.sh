#!/bin/bash
# Setup GitHub OIDC Role for CI/CD deployment
# Run this once to create the IAM role that GitHub Actions will assume
#
# Prerequisites: AWS CLI configured with admin access
# Usage: ./scripts/setup-github-oidc.sh

set -e

PROJECT_NAME="aws-architect-ai"
GITHUB_REPO="Oumayma-O/aws-archi-ai"
AWS_REGION="us-east-1"
ROLE_NAME="${PROJECT_NAME}-github-deploy"

echo "🔧 Setting up GitHub OIDC for: ${GITHUB_REPO}"
echo "   Region: ${AWS_REGION}"
echo "   Role: ${ROLE_NAME}"
echo ""

# Step 1: Create OIDC Provider (idempotent - will fail silently if exists)
echo "1️⃣  Creating GitHub OIDC provider..."
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
  2>/dev/null || echo "   (already exists - OK)"

# Get the OIDC provider ARN
OIDC_ARN=$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?ends_with(Arn, 'token.actions.githubusercontent.com')].Arn" --output text)
echo "   OIDC Provider: ${OIDC_ARN}"

# Step 2: Create the trust policy
echo "2️⃣  Creating IAM role..."
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
EOF
)

aws iam create-role \
  --role-name "${ROLE_NAME}" \
  --assume-role-policy-document "${TRUST_POLICY}" \
  --description "GitHub Actions deploy role for ${PROJECT_NAME}" \
  2>/dev/null || echo "   (role already exists - updating trust policy)"

# Update trust policy in case role already existed
aws iam update-assume-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-document "${TRUST_POLICY}"

# Step 3: Attach permissions
echo "3️⃣  Attaching permissions..."

# ECR + ECS + Terraform permissions
DEPLOY_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECR",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECS",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeClusters",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:ListTasks",
        "ecs:DescribeTasks"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "iam:PassedToService": "ecs-tasks.amazonaws.com"
        }
      }
    },
    {
      "Sid": "Terraform",
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "ecs:*",
        "ecr:*",
        "elasticloadbalancing:*",
        "iam:*",
        "logs:*",
        "bedrock:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "github-deploy-policy" \
  --policy-document "${DEPLOY_POLICY}"

# Get the role ARN
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query "Role.Arn" --output text)

echo ""
echo "✅ Done! GitHub OIDC role created."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Role ARN: ${ROLE_ARN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next step: Add this as a GitHub secret:"
echo "   1. Go to: https://github.com/${GITHUB_REPO}/settings/secrets/actions"
echo "   2. Click 'New repository secret'"
echo "   3. Name: AWS_DEPLOY_ROLE_ARN"
echo "   4. Value: ${ROLE_ARN}"
echo ""
