#!/usr/bin/env bash
#
# Builds the Easy Money backend image, pushes it to ECR, and deploys the
# CloudFormation stack. macOS/Linux equivalent of deploy.ps1.
#
# Usage, from anywhere:
#   ./deploy/deploy.sh
#
# Environment overrides:
#   AWS_PROFILE_NAME  AWS CLI profile (default: default)
#   AWS_REGION        Region (default: eu-north-1, the project's Region)
#   CORS_ORIGINS      Frontend origins allowed to call the API

set -euo pipefail

PROFILE="${AWS_PROFILE_NAME:-default}"
REGION="${AWS_REGION:-eu-north-1}"
STACK_NAME="${STACK_NAME:-easy-money-backend}"
REPO_NAME="${REPO_NAME:-easy-money-backend}"

step() { printf '\n==> %s\n' "$1"; }
warn() { printf '!!  %s\n' "$1" >&2; }

# Always operate from the repository root.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# -----------------------------------------------------------------------------
step "Checking prerequisites"

for tool in aws docker; do
  command -v "$tool" >/dev/null || { warn "$tool is not on PATH."; exit 1; }
done

if ! identity=$(aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" --output json 2>&1); then
  warn "Not signed in. Run: aws login --region $REGION --profile $PROFILE"
  warn "$identity"
  exit 1
fi
ACCOUNT_ID=$(printf '%s' "$identity" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')
echo "    Account: $ACCOUNT_ID"
echo "    Region:  $REGION"

docker info >/dev/null 2>&1 || { warn "Docker is not running."; exit 1; }

# -----------------------------------------------------------------------------
step "Reading configuration from .env"

# The image deliberately does not contain .env (see .dockerignore), so secrets
# are read here and stored in SSM rather than baked into the image.
[ -f .env ] || { warn "No .env file found in $(pwd)."; exit 1; }

get_env() { grep -E "^\s*$1=" .env | head -1 | cut -d= -f2- | xargs || true; }

JWT_SECRET=$(get_env JWT_SECRET)
ADMIN_PASSWORD=$(get_env ADMIN_PASSWORD)
ADMIN_USERNAME=$(get_env ADMIN_USERNAME); ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
CORS_ORIGINS="${CORS_ORIGINS:-$(get_env CORS_ORIGINS)}"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173}"

if [ -z "$JWT_SECRET" ] || [ -z "$ADMIN_PASSWORD" ]; then
  warn "JWT_SECRET and ADMIN_PASSWORD must both be set in .env."
  exit 1
fi
if [ "$JWT_SECRET" = "change-me" ] || [ "$ADMIN_PASSWORD" = "change-me" ]; then
  warn "JWT_SECRET or ADMIN_PASSWORD is still the placeholder 'change-me'."
  warn "Anyone who knows the default can mint admin tokens for your API."
fi

# -----------------------------------------------------------------------------
step "Storing secrets in SSM Parameter Store"

aws ssm put-parameter --name /easy-money/JWT_SECRET --value "$JWT_SECRET" \
  --type SecureString --overwrite --profile "$PROFILE" --region "$REGION" >/dev/null
aws ssm put-parameter --name /easy-money/ADMIN_PASSWORD --value "$ADMIN_PASSWORD" \
  --type SecureString --overwrite --profile "$PROFILE" --region "$REGION" >/dev/null
echo "    Stored /easy-money/JWT_SECRET and /easy-money/ADMIN_PASSWORD"

# -----------------------------------------------------------------------------
step "Ensuring the ECR repository exists"

if aws ecr describe-repositories --repository-names "$REPO_NAME" \
     --profile "$PROFILE" --region "$REGION" >/dev/null 2>&1; then
  echo "    Repository $REPO_NAME already exists"
else
  aws ecr create-repository --repository-name "$REPO_NAME" \
    --image-scanning-configuration scanOnPush=true \
    --profile "$PROFILE" --region "$REGION" >/dev/null
  echo "    Created repository $REPO_NAME"
fi

REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
# A unique tag per deploy, so ECS sees a changed task definition and actually
# rolls the service. Reusing :latest would often be a no-op.
TAG=$(date +%Y%m%d-%H%M%S)
IMAGE_URI="$REGISTRY/$REPO_NAME:$TAG"

# -----------------------------------------------------------------------------
step "Building and pushing the image"

aws ecr get-login-password --profile "$PROFILE" --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

# Fargate runs x86_64; building on an Apple Silicon Mac without this produces
# an image that fails to start with an exec format error.
docker build --platform linux/amd64 -t "$IMAGE_URI" -t "$REGISTRY/$REPO_NAME:latest" .
docker push "$IMAGE_URI"
docker push "$REGISTRY/$REPO_NAME:latest" >/dev/null
echo "    Pushed $IMAGE_URI"

# -----------------------------------------------------------------------------
step "Discovering the default VPC and subnets"

VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" --output text --profile "$PROFILE" --region "$REGION")
[ "$VPC_ID" != "None" ] && [ -n "$VPC_ID" ] || { warn "No default VPC in $REGION."; exit 1; }

# The ALB needs at least two subnets in different AZs, and each gets its own
# EFS mount target.
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[?MapPublicIpOnLaunch].SubnetId" --output text \
  --profile "$PROFILE" --region "$REGION" | tr '\t' '\n' | head -2 | paste -sd, -)
if [ "$(printf '%s' "$SUBNET_IDS" | tr ',' '\n' | grep -c .)" -lt 2 ]; then
  warn "Need at least two public subnets in $VPC_ID."
  exit 1
fi
echo "    VPC:     $VPC_ID"
echo "    Subnets: $SUBNET_IDS"

# -----------------------------------------------------------------------------
step "Deploying the CloudFormation stack (~10 minutes the first time)"

if ! aws cloudformation deploy \
  --template-file deploy/cloudformation.yaml \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    "VpcId=$VPC_ID" \
    "SubnetIds=$SUBNET_IDS" \
    "ImageUri=$IMAGE_URI" \
    "CorsOrigins=$CORS_ORIGINS" \
    "AdminUsername=$ADMIN_USERNAME" \
  --profile "$PROFILE" --region "$REGION"; then
  warn "Stack deploy failed. Recent failure events:"
  aws cloudformation describe-stack-events --stack-name "$STACK_NAME" \
    --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
    --output table --profile "$PROFILE" --region "$REGION"
  exit 1
fi

# -----------------------------------------------------------------------------
step "Deployment complete"

aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table \
  --profile "$PROFILE" --region "$REGION"

HEALTH_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='HealthUrl'].OutputValue" --output text \
  --profile "$PROFILE" --region "$REGION")

printf '\nCloudFront takes a few minutes to finish propagating.\n'
printf 'Once it has, check the API with:\n    curl %s\n' "$HEALTH_URL"
