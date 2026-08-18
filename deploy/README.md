# Deploying the Easy Money backend to AWS

One command deploys the whole thing. From the repository root:

```powershell
# Windows / PowerShell
.\deploy\deploy.ps1
```

```bash
# macOS / Linux
./deploy/deploy.sh
```

Re-run the same command after changing code — it builds a new image and rolls
the service over to it.

## Before the first run

1. **Install the AWS CLI v2.** In PowerShell:

   ```powershell
   irm 'https://awscli.amazonaws.com/v2/install.ps1' | iex
   ```

   Then close and reopen PowerShell so the PATH change takes effect.

2. **Install Docker Desktop** and start it.

3. **Sign in.** The project's Region is `eu-north-1`:

   ```powershell
   aws configure set region eu-north-1 --profile default
   aws login --region eu-north-1 --profile default
   ```

   Credentials last 12 hours and renew for 90 days without another browser
   sign-in. Re-run `aws login` when the deploy script reports "Not signed in".

## What gets created

Everything lands in `eu-north-1` except CloudFront, which is global.

| Resource | Purpose |
|---|---|
| ECR repository | Stores the container image |
| ECS Fargate service | Runs the app — one task, no servers to manage |
| EFS filesystem | Holds `data/easymoney.db` and `uploads/` so they survive restarts |
| Application Load Balancer | Health-checks the task and routes traffic to it |
| CloudFront distribution | Public HTTPS endpoint on a `*.cloudfront.net` domain |
| SSM parameters | `JWT_SECRET` and `ADMIN_PASSWORD` as SecureStrings |
| CloudWatch log group | Application logs at `/ecs/easy-money-backend` |

When it finishes, the script prints your API URL. Check it with:

```
curl https://<your-distribution>.cloudfront.net/health
```

The interactive API docs are at `/docs`.

## Why Fargate and not App Runner

App Runner would be the natural fit, but it is **not available in
`eu-north-1`**, and this project can only create Regional resources in its
assigned Region. Fargate is the closest managed equivalent: you hand it a
container image and it runs it, with no servers to patch.

## Why exactly one task

The app stores its data in a SQLite file. SQLite does not tolerate concurrent
writers from two machines sharing one network filesystem, so the service is
pinned to `DesiredCount: 1`, and deployments stop the old task before starting
the new one. That costs a few seconds of downtime per deploy and buys database
integrity.

**This is the main thing to change if the app needs to scale.** Moving to RDS
Postgres would let you raise the task count and get zero-downtime deploys. The
app uses SQLAlchemy, so the change is mostly a new `DATABASE_URL` plus a data
migration.

## Configuration

The deploy script reads `.env` from the repository root and passes the values
through to the running container:

| Variable | Where it ends up |
|---|---|
| `JWT_SECRET` | SSM SecureString, injected as an env var at task start |
| `ADMIN_PASSWORD` | SSM SecureString, injected the same way |
| `ADMIN_USERNAME` | Plain env var on the task definition |
| `CORS_ORIGINS` | Plain env var — **add your frontend's URL here** |

`DATABASE_URL` and `UPLOAD_DIR` are overridden to point at the EFS mounts, so
the local values in `.env` are ignored in AWS.

Note that `.dockerignore` excludes `.env` from the image on purpose. Secrets
reach the container through SSM, never baked into a layer.

To set the frontend origin without editing `.env`:

```powershell
.\deploy\deploy.ps1 -CorsOrigins "https://your-frontend.example.com"
```

### Security note

`.env` is currently committed to this repository, which means `ADMIN_PASSWORD`
and `JWT_SECRET` are readable by anyone who can read the repo. Rotating them is
worth doing before this handles anything real:

```powershell
# Generate a new JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Update `.env`, add it to a `.gitignore`, run `git rm --cached .env`, and
redeploy. The old values stay in git history, so treat them as compromised.

## Costs

Roughly, in `eu-north-1`, at idle:

| Item | Approx. monthly |
|---|---|
| Application Load Balancer | ~$18 |
| Fargate task (0.25 vCPU, 0.5 GB, always on) | ~$9 |
| EFS (a few GB, bursting) | ~$1 |
| CloudFront, ECR, SSM, logs | Pennies at this traffic |
| **Total** | **~$28–30** |

The ALB is the largest line item. If cost matters more than the managed-service
setup, a single `t3.micro` EC2 instance running the same Docker image costs
about $8/month and drops the ALB entirely.

Watch spending in **AWS Settings > Billing**. If the API suddenly starts
returning access-denied errors on calls that used to work, check whether a
spend limit paused the project.

## Operating it

```powershell
# Tail application logs
aws logs tail /ecs/easy-money-backend --follow --profile default --region eu-north-1

# Check service status
aws ecs describe-services --cluster easy-money --services easy-money-backend `
  --profile default --region eu-north-1

# Force a restart without changing code
aws ecs update-service --cluster easy-money --service easy-money-backend `
  --force-new-deployment --profile default --region eu-north-1
```

### Tearing it down

```powershell
aws cloudformation delete-stack --stack-name easy-money-backend `
  --profile default --region eu-north-1
```

The EFS filesystem is deliberately **retained** on delete so a teardown cannot
destroy your database and uploaded images. Delete it by hand in the EFS console
once you are sure you no longer need the data. The ECR repository and its
images also survive, and cost a few cents a month.

## Troubleshooting

**Tasks start and immediately stop.** Check the logs — usually `alembic upgrade
head` failing against the EFS-backed database.

**Health checks fail and the service never stabilizes.** The target group probes
`/health` on port 8000. Confirm the container listens on `0.0.0.0:8000`, which
the Dockerfile's `CMD` already does.

**`exec format error` in the logs.** The image was built for the wrong
architecture. Both deploy scripts pass `--platform linux/amd64` to avoid this.

**CloudFront returns 502.** Give the distribution a few minutes after the first
deploy. If it persists, hit the `LoadBalancerDns` output directly over plain
HTTP to find out whether the problem is the origin or the distribution.
