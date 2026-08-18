<#
.SYNOPSIS
    Builds the Easy Money backend image in AWS CodeBuild and deploys it to
    ECS Fargate.

.DESCRIPTION
    Run this from anywhere on a machine that has the AWS CLI installed and has
    already run `aws login`. Docker is NOT required — the image is built in
    AWS, not locally.

        .\deploy\deploy.ps1

    The script is idempotent: run it again after changing the code and it
    builds a new image and rolls the service over to it.

.PARAMETER Profile
    AWS CLI profile to use. Defaults to "default".

.PARAMETER Region
    AWS Region. Defaults to eu-north-1, the project's assigned Region.

.PARAMETER CorsOrigins
    Comma-separated frontend origins allowed to call the API. Defaults to the
    value in .env.
#>
[CmdletBinding()]
param(
    [string]$Profile = "default",
    [string]$Region = "eu-north-1",
    [string]$StackName = "easy-money-backend",
    [string]$BuildStackName = "easy-money-build",
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

    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        throw "The AWS CLI is not on PATH. Install it and open a new PowerShell window."
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
    Step "Deploying the build pipeline"

    aws cloudformation deploy `
        --template-file "deploy/build-stack.yaml" `
        --stack-name $BuildStackName `
        --capabilities CAPABILITY_IAM `
        --profile $Profile --region $Region
    if ($LASTEXITCODE -ne 0) { throw "Build stack deploy failed." }

    $buildOutputs = aws cloudformation describe-stacks --stack-name $BuildStackName `
        --query "Stacks[0].Outputs" --output json --profile $Profile --region $Region | ConvertFrom-Json
    $RepoUri      = ($buildOutputs | Where-Object { $_.OutputKey -eq "RepositoryUri" }).OutputValue
    $SourceBucket = ($buildOutputs | Where-Object { $_.OutputKey -eq "SourceBucketName" }).OutputValue
    $BuildProject = ($buildOutputs | Where-Object { $_.OutputKey -eq "BuildProjectName" }).OutputValue
    Write-Host "    Repository: $RepoUri"
    Write-Host "    Source:     s3://$SourceBucket"

    # -------------------------------------------------------------------------
    Step "Packaging source"

    # A unique tag per deploy, so ECS sees a changed task definition and
    # actually rolls the service. Reusing :latest would often be a no-op.
    $Tag = Get-Date -Format "yyyyMMdd-HHmmss"
    $SourceKey = "source-$Tag.zip"
    $Staging = Join-Path $env:TEMP "easy-money-src-$Tag"
    $ZipPath = Join-Path $env:TEMP $SourceKey

    # Copy the working tree, minus directories that must never reach the build:
    # .git is large, and data/ and uploads/ hold local state that the running
    # app keeps on EFS instead.
    $null = robocopy $RepoRoot $Staging /E `
        /XD .git data uploads .venv venv __pycache__ .pytest_cache node_modules `
        /XF "*.pyc" "*.db" "*.db-wal" "*.db-shm" `
        /NFL /NDL /NJH /NJS /NP
    # robocopy uses exit codes 0-7 for success; 8 and above are real failures.
    if ($LASTEXITCODE -ge 8) { throw "Failed to stage source (robocopy exit $LASTEXITCODE)." }
    $global:LASTEXITCODE = 0

    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Compress-Archive -Path "$Staging\*" -DestinationPath $ZipPath -Force
    Remove-Item $Staging -Recurse -Force
    $sizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
    Write-Host "    Packaged $sizeMb MB"

    aws s3 cp $ZipPath "s3://$SourceBucket/$SourceKey" --profile $Profile --region $Region | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to upload source to S3." }
    Remove-Item $ZipPath -Force
    Write-Host "    Uploaded s3://$SourceBucket/$SourceKey"

    # -------------------------------------------------------------------------
    Step "Building the image in CodeBuild (a few minutes)"

    $BuildId = aws codebuild start-build `
        --project-name $BuildProject `
        --source-location-override "$SourceBucket/$SourceKey" `
        --environment-variables-override "name=IMAGE_TAG,value=$Tag,type=PLAINTEXT" `
        --query "build.id" --output text `
        --profile $Profile --region $Region
    if ($LASTEXITCODE -ne 0) { throw "Failed to start the build." }
    Write-Host "    Build: $BuildId"

    $status = "IN_PROGRESS"
    while ($status -eq "IN_PROGRESS") {
        Start-Sleep -Seconds 15
        $status = aws codebuild batch-get-builds --ids $BuildId `
            --query "builds[0].buildStatus" --output text `
            --profile $Profile --region $Region
        Write-Host "    $status"
    }

    if ($status -ne "SUCCEEDED") {
        Warn "Build $status. Last 40 log lines:"
        $logs = aws codebuild batch-get-builds --ids $BuildId `
            --query "builds[0].logs.[groupName,streamName]" --output text `
            --profile $Profile --region $Region
        $group, $stream = $logs -split "\s+"
        if ($group -and $group -ne "None") {
            aws logs get-log-events --log-group-name $group --log-stream-name $stream `
                --limit 40 --query "events[].message" --output text `
                --profile $Profile --region $Region
        }
        throw "CodeBuild did not succeed."
    }

    $ImageUri = "${RepoUri}:$Tag"
    Write-Host "    Built $ImageUri"

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
    Step "Deploying the application stack (~10 minutes the first time)"

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
    Write-Host "    curl.exe $healthUrl"
}
finally {
    Pop-Location
}
