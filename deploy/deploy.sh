#!/usr/bin/env bash
#
# Builds the Easy Money backend image in AWS CodeBuild and deploys it to ECS
# Fargate. macOS/Linux equivalent of deploy.ps1. Docker is NOT required.
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
BUILD_STACK_NAME="${BUILD_STACK_NAME:-easy-money-build}"

step() { printf '\n==> %s\n' "$1"; }
warn() { printf '!!  %s\n' "$1" >&2; }

# Always operate from the repository root.
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT=$(pwd)

# -----------------------------------------------------------------------------
step "Checking prerequisites"

command -v aws >/dev/null || { warn "The AWS CLI is not on PATH."; exit 1; }
command -v zip >/dev/null || { warn "zip is not on PATH."; exit 1; }

if ! identity=$(aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" --output json 2>&1); then
  warn "Not signed in. Run: aws login --region $REGION --profile $PROFILE"
  warn "$identity"
  exit 1
fi
ACCOUNT_ID=$(printf '%s' "$identity" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')
echo "    Account: $ACCOUNT_ID"
echo "    Region:  $REGION"

# -----------------------------------------------------------------------------
step "Reading configuration from .env"

# The image deliberately does not contain .env (see .dockerignore), so secrets
# are read here and stored in SSM rather than baked into the image.
[ -f .env ] || { warn "No .env file found in $REPO_ROOT."; exit 1; }

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
step "Deploying the build pipeline"

aws cloudformation deploy \
  --template-file deploy/build-stack.yaml \
  --stack-name "$BUILD_STACK_NAME" \
  --capabilities CAPABILITY_IAM \
  --profile "$PROFILE" --region "$REGION"

stack_output() {
  aws cloudformation describe-stacks --stack-name "$BUILD_STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text \
    --profile "$PROFILE" --region "$REGION"
}
REPO_URI=$(stack_output RepositoryUri)
SOURCE_BUCKET=$(stack_output SourceBucketName)
BUILD_PROJECT=$(stack_output BuildProjectName)
echo "    Repository: $REPO_URI"
echo "    Source:     s3://$SOURCE_BUCKET"

# -----------------------------------------------------------------------------
step "Packaging source"

# A unique tag per deploy, so ECS sees a changed task definition and actually
# rolls the service. Reusing :latest would often be a no-op.
TAG=$(date +%Y%m%d-%H%M%S)
SOURCE_KEY="source-$TAG.zip"
ZIP_PATH="${TMPDIR:-/tmp}/$SOURCE_KEY"
rm -f "$ZIP_PATH"

# Exclude directories that must never reach the build: .git is large, and
# data/ and uploads/ hold local state the running app keeps on EFS instead.
zip -qr "$ZIP_PATH" . \
  -x '.git/*' 'data/*' 'uploads/*' '.venv/*' 'venv/*' \
     '*__pycache__/*' '*.pyc' '.pytest_cache/*' 'node_modules/*' \
     '*.db' '*.db-wal' '*.db-shm'
echo "    Packaged $(du -h "$ZIP_PATH" | cut -f1)"

aws s3 cp "$ZIP_PATH" "s3://$SOURCE_BUCKET/$SOURCE_KEY" \
  --profile "$PROFILE" --region "$REGION" >/dev/null
rm -f "$ZIP_PATH"
echo "    Uploaded s3://$SOURCE_BUCKET/$SOURCE_KEY"

# -----------------------------------------------------------------------------
step "Building the image in CodeBuild (a few minutes)"

BUILD_ID=$(aws codebuild start-build \
  --project-name "$BUILD_PROJECT" \
  --source-location-override "$SOURCE_BUCKET/$SOURCE_KEY" \
  --environment-variables-override "name=IMAGE_TAG,value=$TAG,type=PLAINTEXT" \
  --query "build.id" --output text \
  --profile "$PROFILE" --region "$REGION")
echo "    Build: $BUILD_ID"

STATUS=IN_PROGRESS
while [ "$STATUS" = "IN_PROGRESS" ]; do
  sleep 15
  STATUS=$(aws codebuild batch-get-builds --ids "$BUILD_ID" \
    --query "builds[0].buildStatus" --output text \
    --profile "$PROFILE" --region "$REGION")
  echo "    $STATUS"
done

if [ "$STATUS" != "SUCCEEDED" ]; then
  warn "Build $STATUS. Last 40 log lines:"
  read -r LOG_GROUP LOG_STREAM <<<"$(aws codebuild batch-get-builds --ids "$BUILD_ID" \
    --query "builds[0].logs.[groupName,streamName]" --output text \
    --profile "$PROFILE" --region "$REGION")"
  if [ -n "$LOG_GROUP" ] && [ "$LOG_GROUP" != "None" ]; then
    aws logs get-log-events --log-group-name "$LOG_GROUP" --log-stream-name "$LOG_STREAM" \
      --limit 40 --query "events[].message" --output text \
      --profile "$PROFILE" --region "$REGION"
  fi
  exit 1
fi

IMAGE_URI="$REPO_URI:$TAG"
echo "    Built $IMAGE_URI"

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
step "Deploying the application stack (~10 minutes the first time)"

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
