<#
.SYNOPSIS
    Builds the Easy Money backend image, pushes it to ECR, and deploys the
    CloudFormation stack.

.DESCRIPTION
    Run this from the repository root on a machine that has the AWS CLI and
    Docker Desktop installed, and that has already run `aws login`.

        .\deploy\deploy.ps1

    The script is idempotent: run it again after changing the code and it
    builds a new image, pushes it, and rolls the service over to it.

.PARAMETER Profile
    AWS CLI profile to use. Defaults to "default".

.PARAMETER Region
    AWS Region. Defaults to eu-north-1, the project's assigned Region.

.PARAMETER CorsOrigins
    Comma-separated frontend origins allowed to call the API.
#>
[CmdletBinding()]
param(
    [string]$Profile = "default",
    [string]$Region = "eu-north-1",
    [string]$StackName = "easy-money-backend",
    [string]$RepoName = "easy-money-backend",
    [string]$CorsOrigins = ""
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }

# Always operate from the repository root, regardless of where this is invoked.
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    # -------------------------------------------------------------------------
    Step "Checking prerequisites"

    foreach ($tool in @("aws", "docker")) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "$tool is not on PATH. Install it and open a new PowerShell window."
        }
    }

    # Fails fast with a clear message if the login has expired, rather than
    # letting a later step produce a confusing error.
    $identity = aws sts get-caller-identity --profile $Profile --region $Region --output json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Not signed in. Run: aws login --region $Region --profile $Profile`n$identity"
    }
    $AccountId = ($identity | ConvertFrom-Json).Account
    Write-Host "    Account: $AccountId"
    Write-Host "    Region:  $Region"

    docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw "Docker is installed but not running. Start Docker Desktop." }

    # -------------------------------------------------------------------------
    Step "Reading configuration from .env"

    # The image deliberately does not contain .env (see .dockerignore), so the
    # secrets are read here and stored in SSM instead of being baked in.
    if (-not (Test-Path ".env")) { throw "No .env file found in $RepoRoot." }

    $envVars = @{}
    foreach ($line in Get-Content ".env") {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $name, $value = $line -split '=', 2
        $envVars[$name.Trim()] = $value.Trim()
    }

    $JwtSecret     = $envVars["JWT_SECRET"]
    $AdminPassword = $envVars["ADMIN_PASSWORD"]
    $AdminUsername = if ($envVars["ADMIN_USERNAME"]) { $envVars["ADMIN_USERNAME"] } else { "admin" }
    if (-not $CorsOrigins) {
        $CorsOrigins = if ($envVars["CORS_ORIGINS"]) { $envVars["CORS_ORIGINS"] } else { "http://localhost:5173" }
    }

    if (-not $JwtSecret -or -not $AdminPassword) {
        throw "JWT_SECRET and ADMIN_PASSWORD must both be set in .env."
    }
    if ($JwtSecret -eq "change-me" -or $AdminPassword -eq "change-me") {
        Warn "JWT_SECRET or ADMIN_PASSWORD is still the placeholder 'change-me'."
        Warn "Anyone who knows the default can mint admin tokens for your API."
    }

    # -------------------------------------------------------------------------
    Step "Storing secrets in SSM Parameter Store"

    aws ssm put-parameter --name "/easy-money/JWT_SECRET" --value $JwtSecret `
        --type SecureString --overwrite --profile $Profile --region $Region | Out-Null
    aws ssm put-parameter --name "/easy-money/ADMIN_PASSWORD" --value $AdminPassword `
        --type SecureString --overwrite --profile $Profile --region $Region | Out-Null
    Write-Host "    Stored /easy-money/JWT_SECRET and /easy-money/ADMIN_PASSWORD"

    # -------------------------------------------------------------------------
    Step "Ensuring the ECR repository exists"

    aws ecr describe-repositories --repository-names $RepoName `
        --profile $Profile --region $Region *> $null
    if ($LASTEXITCODE -ne 0) {
        aws ecr create-repository --repository-name $RepoName `
            --image-scanning-configuration scanOnPush=true `
            --profile $Profile --region $Region | Out-Null
        Write-Host "    Created repository $RepoName"
    } else {
        Write-Host "    Repository $RepoName already exists"
    }

    $Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
    # A unique tag per deploy, so ECS always sees a changed task definition and
    # actually rolls the service. Reusing :latest would often be a no-op.
    $Tag = Get-Date -Format "yyyyMMdd-HHmmss"
    $ImageUri = "$Registry/${RepoName}:$Tag"

    # -------------------------------------------------------------------------
    Step "Building and pushing the image"

    aws ecr get-login-password --profile $Profile --region $Region |
        docker login --username AWS --password-stdin $Registry
    if ($LASTEXITCODE -ne 0) { throw "docker login to ECR failed." }

    # Fargate runs on x86_64; building on an ARM machine without this produces
    # an image that fails to start with an exec format error.
    docker build --platform linux/amd64 -t $ImageUri -t "$Registry/${RepoName}:latest" .
    if ($LASTEXITCODE -ne 0) { throw "docker build failed." }

    docker push $ImageUri
    if ($LASTEXITCODE -ne 0) { throw "docker push failed." }
    docker push "$Registry/${RepoName}:latest" | Out-Null
    Write-Host "    Pushed $ImageUri"

    # -------------------------------------------------------------------------
    Step "Discovering the default VPC and subnets"

    $VpcId = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" `
        --query "Vpcs[0].VpcId" --output text --profile $Profile --region $Region
    if (-not $VpcId -or $VpcId -eq "None") {
        throw "No default VPC found in $Region. Create one, or pass an explicit VpcId."
    }

    # Two subnets in different AZs: the ALB requires at least two, and each
    # gets its own EFS mount target.
    $SubnetList = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" `
        --query "Subnets[?MapPublicIpOnLaunch].SubnetId" --output text `
        --profile $Profile --region $Region
    $Subnets = ($SubnetList -split "\s+" | Where-Object { $_ }) | Select-Object -First 2
    if ($Subnets.Count -lt 2) {
        throw "Need at least two public subnets in $VpcId, found $($Subnets.Count)."
    }
    $SubnetIds = $Subnets -join ","
    Write-Host "    VPC:     $VpcId"
    Write-Host "    Subnets: $SubnetIds"

    # -------------------------------------------------------------------------
    Step "Deploying the CloudFormation stack (this takes ~10 minutes the first time)"

    aws cloudformation deploy `
        --template-file "deploy/cloudformation.yaml" `
        --stack-name $StackName `
        --capabilities CAPABILITY_IAM `
        --parameter-overrides `
            "VpcId=$VpcId" `
            "SubnetIds=$SubnetIds" `
            "ImageUri=$ImageUri" `
            "CorsOrigins=$CorsOrigins" `
            "AdminUsername=$AdminUsername" `
        --profile $Profile --region $Region
    if ($LASTEXITCODE -ne 0) {
        Warn "Stack deploy failed. Recent failure events:"
        aws cloudformation describe-stack-events --stack-name $StackName `
            --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED'].[LogicalResourceId,ResourceStatusReason]" `
            --output table --profile $Profile --region $Region
        throw "CloudFormation deploy failed."
    }

    # -------------------------------------------------------------------------
    Step "Deployment complete"

    $outputs = aws cloudformation describe-stacks --stack-name $StackName `
        --query "Stacks[0].Outputs" --output json --profile $Profile --region $Region | ConvertFrom-Json

    foreach ($o in $outputs) {
        Write-Host ("    {0,-18} {1}" -f $o.OutputKey, $o.OutputValue)
    }

    $healthUrl = ($outputs | Where-Object { $_.OutputKey -eq "HealthUrl" }).OutputValue
    Write-Host "`nCloudFront takes a few minutes to finish propagating." -ForegroundColor Yellow
    Write-Host "Once it has, check the API with:" -ForegroundColor Yellow
    Write-Host "    curl $healthUrl"
}
finally {
    Pop-Location
}
