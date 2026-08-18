# Easy Money — Frontend Build Prompt (React + Spec Kit)

## 1. Project context

We are building **Easy Money**, a simulated stock-market system for **Avamina Scouting Group (ASG)**, a Coptic church scouting group. It runs during a camp: participants "trade" ETFs in the camp currency **لحوح**, and a large screen shows live prices.

The **backend already exists and is finished** (FastAPI + SQLite, in this repository). The **UI design is already finished**. This task is to build the **React frontend** against the existing API, using **Spec Kit** for a spec-driven workflow.

**Do not modify the backend.** Its HTTP contract — routes, methods, request/response field names and types, status codes, error envelope — is fixed. If you believe the frontend needs something the API does not expose, say so explicitly and work around it in the client; do not change backend code, schemas, or migrations.

### Product rules

- Exactly **7 ETFs**. They are seeded by the backend with fixed IDs `1..7`. They cannot be created or deleted — only renamed, re-logoed, and revalued.
- Currency is **لحوح**. Never hardcode it in components — every money-bearing API response carries a `currency` field; render that.
- Each ETF has a changeable **name**, **logo**, and **value**.
- Values are updated **manually (absolute)** or **by percentage**.
- Value increased → **green** trend. Value decreased → **red** trend. Unchanged → neutral.
- **Public dashboard** is shown mainly on a **large screen** during the camp — that is the priority experience.
- **Admin dashboard** must work well on **mobile** — that is the priority there.
- **One admin account only.** Credentials come from backend env; there is no signup, no password reset, no user management UI.
- Participants submit **BUY/SELL requests** from a public form.
- The request form requires: **requester name, ETF, quantity (units), BUY/SELL type, and an image**.
- The backend records the **submission time** and the **ETF value at the moment of submission** — the client must not compute or send these.
- Admin **reviews and approves/rejects** requests.

### Branding

- Easy Money
- Avamina Scouting Group — ASG
- **The existing finished design must be followed closely** (it lives in Claude Design — see §2). Do not redesign it unless required for responsive behavior.

---

## 2. The finished design — import it first

The UI design is **already finished** and lives in a Claude Design project. It is the visual source of truth for this frontend. Import and read it **before** writing the spec, and keep it open while implementing.

Use the **claude_design MCP** (`https://api.anthropic.com/v1/design/mcp`, authenticate via `/design-login`) to import this project:

**https://claude.ai/design/p/59965c17-a894-4543-8c2c-a6f57259df89?file=Stock+Market+Projector.dc.html**

Focus on these files (the whole project is readable):

- `Stock Market Projector.dc.html`

Also read the file the selection imports:

- `support.js`

**Implement:** `Stock Market Projector.dc.html`.

If the design MCP is not reachable in your environment (no interactive terminal for `/design-login`, or design authorization is not granted), get the files into the workspace instead — via Claude Design's **"Send to Claude Code Web"**, which seeds the project into the working directory, or by having the files provided directly. **Do not start implementing the UI from imagination** — stop and get the design first.

### How to use it

- `Stock Market Projector.dc.html` is the **public projector/large-screen dashboard**. Treat its layout, type scale, spacing, color tokens, trend colors, and motion as the specification for the public view.
- Extract the design's **tokens** (colors, typography, spacing, radii, shadows, the up/down/flat trend colors) into the frontend's styling layer once, and build every component — public *and* admin — from those tokens. The admin screens must look like they belong to the same product even where the design does not cover them directly.
- `support.js` carries the behavior the design file relies on. Read it to understand intended interactions and animations (e.g. how values transition when a price changes), then reimplement that behavior idiomatically in React — do not ship the design file's script as-is.
- The design is authored as a static artboard with placeholder data. Replace the placeholders with live API data (§5) — **without** altering the layout or visual language.
- **Follow the design closely. Do not redesign it.** The only changes permitted are those genuinely required for responsive behavior (notably the mobile-first admin pages, which the projector design does not cover) — and those must extend the design's own language rather than introduce a new one.
- Where the design shows something the API cannot supply (see §5.5), keep the visual treatment and fill it from what the API *does* return, or drop that element cleanly. Never invent a backend endpoint to satisfy a mockup.

---

## 3. Execution model — orchestra mode with subagents

Run this build in **orchestra mode**. The main session is the **conductor**, not the bricklayer: it owns the spec, the plan, the task graph, integration, and verification. Feature code is written by **subagents** it dispatches.

### Model and effort per role

| Work | Subagent model | Reasoning effort |
|---|---|---|
| **Implementation — writing code** (components, pages, API client, hooks, styles, tests, config) | **Sonnet** | **low** |
| **Everything else** (repo/API inspection, design import and token extraction, spec and plan drafting, task decomposition, review, integration checks, debugging analysis) | **Opus** | **low** |

Spawn with the agent tool, setting `model` explicitly on every dispatch — `model: "sonnet"` for implementation, `model: "opus"` for all other roles. Never let a subagent inherit the model by default; state it every time.

### How the conductor works

1. **Think first, at the top.** The conductor reads the backend contract (§5) and the design (§2) itself — or via an Opus research subagent — before any code task exists. No implementation subagent is dispatched against an unexplored area.
2. **Decompose to bounded units.** Every implementation task handed to a Sonnet subagent must be small enough to finish in one pass and fully specified: exact files to create or modify, the relevant contract excerpt inlined (endpoint, payload shape, error codes), the design tokens or component it must match, and explicit acceptance criteria. **A Sonnet-at-low-effort subagent is an executor, not an explorer** — if a task needs discovery or judgment, do that discovery first (Opus) and pass the conclusions down.
3. **Sequence the foundations, then fan out.** Build the shared layer serially — design tokens, API client, type definitions, auth handling, routing shell, shared UI primitives — because everything else depends on it. Only after it is stable, dispatch page-level work in **parallel**, and only where tasks touch **disjoint files**. Two subagents editing the same file is a merge conflict you created yourself.
4. **Verify every hand-back.** Do not take a subagent's report at face value. After each returned task the conductor runs the real checks — typecheck, lint, build, and the relevant tests — and reads the diff. If it fails, re-dispatch with the failure output included rather than patching around it.
5. **Review with Opus.** Before marking a slice done, dispatch an Opus review subagent over the diff for contract drift (a field renamed, a number parsed out of a money string, a hardcoded URL, a missing loading/error state). Fixes from the review go back to a Sonnet subagent.
6. **The conductor keeps the state.** Spec, plan, task list, and progress live in the main session and in `specs/`. Subagents start cold every time and share no memory — restate the context each dispatch instead of assuming continuity.
7. **Escalate rather than guess.** A subagent that hits a genuine ambiguity reports back to the conductor; the conductor decides. Subagents do not invent backend endpoints, redesign UI, or widen scope on their own.

### Mapping to the Spec Kit phases (§4)

- `/constitution`, `/specify`, `/clarify`, `/plan`, `/tasks`, `/analyze` → conductor, with **Opus** subagents for parallel research (backend contract sweep, design token extraction, dependency/tooling checks).
- `/implement` → conductor drives the task list, dispatching **Sonnet** subagents per task and verifying each result before moving on.

---

## 4. Workflow: use Spec Kit

Build this feature with **[Spec Kit](https://github.com/github/spec-kit)** (spec-driven development). Do not jump straight to writing components. The conductor (§3) owns these phases and runs the slash commands; subagents execute the work they generate.

### Setup

```bash
# Initialize Spec Kit for this repo, targeting Claude as the agent
uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai claude
# (or: specify init easy-money-frontend --ai claude  to scaffold in a subfolder)
```

This creates `.specify/` (templates, scripts, memory) and registers the slash commands.

### Run the phases in order

1. **`/constitution`** — establish the project's non-negotiables. At minimum encode:
   - The backend contract is read-only; the frontend adapts to it.
   - The finished design is authoritative; responsive adaptation only.
   - Every data view handles **loading / empty / success / error** states.
   - No hardcoded URLs; all environment-specific values come from env vars.
   - Reusable components over per-page duplication.
2. **`/specify`** — write the feature spec: public dashboard, request submission, admin login, admin ETF management, admin request review. Describe **what** and **why**, not implementation.
3. **`/clarify`** — resolve ambiguities against the codebase, not by asking the user. Inspect `app/api/routes/`, `app/schemas/`, and `app/models/` and record what you found. Only surface a question if a wrong guess would make the work useless.
4. **`/plan`** — the technical plan. Pin the stack (see §6), the folder structure, the API client layer, state/data-fetching approach, routing, and the env-var contract.
5. **`/tasks`** — generate the ordered, dependency-aware task list.
6. **`/analyze`** — cross-check spec ↔ plan ↔ tasks for gaps and contradictions before writing code.
7. **`/implement`** — execute the tasks.

Keep `specs/<feature>/spec.md`, `plan.md`, and `tasks.md` committed alongside the code so the spec history is reviewable.

---

## 5. Backend instructions (the contract you are building against)

### 5.1 Running the backend locally

```bash
cp .env.example .env          # then edit ADMIN_PASSWORD and JWT_SECRET
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload  # http://127.0.0.1:8000
```

Interactive API docs: `http://127.0.0.1:8000/docs` (OpenAPI schema at `/openapi.json` — use it to generate or verify types).

On startup the backend idempotently seeds the single admin and the seven ETFs (IDs `1..7`, name `"ETF n"`, value `0`, no logo), and creates `uploads/etfs/` and `uploads/requests/`.

Backend env vars that affect the frontend:

| Variable | Effect on frontend |
|---|---|
| `CORS_ORIGINS` | Comma-separated allowlist. **Must contain the frontend's exact origin** (default `http://localhost:5173`). Never `*` — credentials are allowed. Add the deployed frontend URL before deploying. |
| `MAX_UPLOAD_MB` | Max image size, default `5`. Validate client-side against the same number. |
| `CURRENCY` | Default `لحوح`; echoed in responses as `currency`. |
| `JWT_EXPIRE_MINUTES` | Token lifetime, default `720` (12h). |

### 5.2 Conventions that apply to every endpoint

- All app routes are under **`/api`**. The only exception is **`GET /health`** → `{"status":"ok","version":"0.1.0"}`.
- **Auth**: JWT bearer. Send `Authorization: Bearer <access_token>` on every admin route. There are no cookies and no refresh token.
- **All money and percentage fields are serialized as fixed 2-decimal *strings*** (`"1234.50"`, `"-3.25"`), not numbers. Render them as-is; only parse when you need to compare or compute, and never re-serialize a parsed float back into a display.
- **All timestamps are ISO-8601 UTC with an explicit `Z`** (e.g. `2026-08-18T17:56:00Z`). Convert to local time for display.
- **Image URLs (`logo_url`, `requester_image_url`) are server-relative** (`/uploads/etfs/<file>.jpg`). Prefix them with the API base origin before use — in production the frontend and backend are different origins, so a bare relative path will 404.
- **Error envelope** — every error has this exact shape:
  ```json
  { "error": { "code": "ETF_NOT_FOUND", "message": "ETF 9 does not exist", "details": null } }
  ```
  Build one error parser and use it everywhere. Known codes:

  | HTTP | `code` | Meaning / UI handling |
  |---|---|---|
  | 401 | `UNAUTHORIZED` | Missing, invalid, or expired token → clear stored token, redirect to admin login |
  | 404 | `ETF_NOT_FOUND` | Unknown ETF id |
  | 404 | `REQUEST_NOT_FOUND` | Unknown trade request id |
  | 400 | `UNSUPPORTED_IMAGE_TYPE` | Not JPEG/PNG/WEBP, empty, or content doesn't match declared type |
  | 400 | `ZERO_VALUE_PERCENTAGE` | Percentage adjust attempted on an ETF whose value is `0` |
  | 413 | `FILE_TOO_LARGE` | Image over `MAX_UPLOAD_MB` |
  | 422 | `VALIDATION_ERROR` | Bad input; `details` holds the raw validator output (do not show it verbatim to participants) |
  | 500 | `INTERNAL_ERROR` | Generic failure |

- **Uploads accept only** `image/jpeg`, `image/png`, `image/webp`. The backend sniffs magic bytes, so a renamed file is rejected — validate type and size client-side first for a fast, friendly error.

### 5.3 Public endpoints (no auth)

**`GET /api/etfs`** → `ETF[]`, ordered by `id`.
**`GET /api/etfs/{id}`** → `ETF`.

```jsonc
// ETF
{
  "id": 1,
  "name": "ETF 1",
  "logo_url": "/uploads/etfs/ab12….jpg",   // nullable — handle the no-logo case
  "current_value": "120.00",
  "previous_value": "100.00",
  "last_change_amount": "20.00",           // may be negative
  "last_change_percentage": "20.00",       // may be negative
  "trend": "UP",                           // "UP" | "DOWN" | "FLAT"
  "updated_at": "2026-08-18T17:56:00Z",
  "currency": "لحوح"
}
```

Drive green/red/neutral off **`trend`**, not off a sign you compute yourself.

**`GET /api/etfs/{id}/history?limit=200`** → value-change history, **ascending by `created_at`** (oldest first — chart-ready). `limit` defaults to `200`, max `1000`.

```jsonc
{
  "id": 12, "etf_id": 1,
  "old_value": "100.00", "new_value": "120.00",
  "change_amount": "20.00", "change_percentage": "20.00",
  "change_type": "PERCENTAGE",   // "ABSOLUTE" | "PERCENTAGE"
  "input_value": "20.00",        // the number the admin typed
  "created_at": "2026-08-18T17:56:00Z"
}
```

**`POST /api/requests`** → `201` + `TradeRequest`. **`multipart/form-data`** (never JSON):

| Field | Type | Notes |
|---|---|---|
| `requester_name` | text | Non-empty after trimming; max 120 chars |
| `etf_id` | integer | One of the 7 |
| `request_type` | text | `BUY` or `SELL`, uppercase exactly |
| `units` | decimal | **Strictly positive**; 2 decimal places |
| `requester_image` | file | JPEG/PNG/WEBP, ≤ `MAX_UPLOAD_MB` |

Do **not** send a timestamp or a price — the backend stamps `created_at` and snapshots the ETF's `current_value` server-side. The response echoes both, so the success screen can show the participant exactly what was locked in.

```jsonc
// TradeRequest
{
  "id": 5,
  "requester_name": "Mina",
  "requester_image_url": "/uploads/requests/cd34….png",
  "etf_id": 1, "etf_name": "ETF 1",
  "request_type": "BUY",                  // "BUY" | "SELL"
  "units": "3.00",
  "etf_value_snapshot": "120.00",         // price at submission time
  "total_value_snapshot": "360.00",       // units × snapshot, server-computed
  "status": "PENDING",                    // "PENDING" | "APPROVED" | "REJECTED"
  "currency": "لحوح",
  "created_at": "2026-08-18T17:56:00Z",
  "processed_at": null                    // set when approved/rejected
}
```

> There is **no public endpoint to list or look up submitted requests**. A participant sees their request exactly once, in the response to their own submission. Design the success state accordingly (show the full receipt then and there); do not build a "my requests" view or a lookup-by-name screen.

### 5.4 Admin endpoints (Bearer token required)

**`POST /api/auth/login`** — JSON `{ "username", "password" }` → `{ "access_token", "token_type": "bearer", "expires_in": 43200 }`. Wrong credentials → `401 UNAUTHORIZED`.

**`GET /api/auth/me`** → `{ "id", "username" }`. Use it on app load to validate a stored token before showing the admin shell.

**`PATCH /api/admin/etfs/{id}`** — JSON `{ "name": "..." }` → updated `ETF`. Empty/whitespace name → `422`.

**`POST /api/admin/etfs/{id}/value`** — JSON `{ "value": 150.00 }` → updated `ETF`. Absolute set; must be `>= 0`. Records history as `ABSOLUTE`.

**`POST /api/admin/etfs/{id}/adjust`** — JSON `{ "percentage": -10 }` → updated `ETF`. Positive or negative. **Fails with `400 ZERO_VALUE_PERCENTAGE` when the ETF's current value is `0`** — disable the percentage control (with an explanatory hint) for zero-valued ETFs instead of letting the admin hit the error. Records history as `PERCENTAGE`.

**`POST /api/admin/etfs/{id}/logo`** — `multipart/form-data`, field name **`file`** → updated `ETF` with the new `logo_url`. Replacing a logo does not delete the old file.

**`GET /api/admin/requests`** → `TradeRequest[]`, **newest first**. Query params (all optional): `status` (`PENDING`|`APPROVED`|`REJECTED`), `request_type` (`BUY`|`SELL`), `etf_id`, `limit` (default `100`, **max `500`**), `offset` (default `0`). Pagination is offset-based; there is no total count in the response, so infer "has more" from a full page.

**`GET /api/admin/requests/{id}`** → one `TradeRequest`.

**`PATCH /api/admin/requests/{id}/status`** — JSON `{ "status": "APPROVED" }` → updated `TradeRequest`. Accepts `PENDING`, `APPROVED`, `REJECTED`. Approving/rejecting sets `processed_at`; setting it back to `PENDING` clears it. **This is not idempotent-guarded** — the backend does not block re-deciding an already-decided request, so the UI should confirm before changing a decision that has already been made.

### 5.5 What the backend does *not* do

Plan around these; do not add backend endpoints for them.

- **No WebSockets, no SSE.** The public dashboard must **poll `GET /api/etfs`** (10–15s is a sane interval for a camp screen). Poll on an interval that survives tab-visibility changes, and never let a failed poll blank out the last-good data — keep showing the last values with a subtle "reconnecting" indicator.
- **No portfolio/holdings model.** Approving a request does not move units or money anywhere. It is a review workflow only. Don't imply balances in the UI.
- **No ETF create/delete.** Exactly 7, always.
- **No public request listing** (see §5.3).
- **No refresh tokens.** When the JWT expires the next admin call returns `401`; handle it globally by clearing the token and redirecting to login.
- **Seeded ETFs start at value `0` with no logo and generic names.** The public dashboard must look correct in that pre-camp state — that is a real empty state, not an edge case.

---

## 6. Frontend requirements

- **React** (Vite). TypeScript preferred; generate types from `/openapi.json` or hand-write them to match §5 exactly.
- **Connect to the existing FastAPI API** — one thin API client module that owns the base URL, auth header injection, multipart handling, error-envelope parsing, and image-URL absolutization. Components never call `fetch` directly.
- **Clean, reusable components.** ETF card, trend indicator, money display, image uploader, status badge, form field, empty/error/loading states — build them once.
- **Handle loading, empty, success, and error states properly** in every view. No spinner-forever, no silent failure, no raw validator JSON shown to a participant.
- **Public screen prioritizes the large-screen experience**: readable from a distance, high-contrast trend colors, generous type scale, a layout that fits all 7 ETFs at once without scrolling on a 1080p/4K display.
- **Admin pages prioritize responsive mobile usability**: thumb-reachable controls, a decision flow that works one-handed, no horizontal scrolling, image previews that don't blow up the layout.
- Arabic currency name and any Arabic copy must render correctly (font + direction) inside the existing design.

## 7. Deployment

- Frontend and backend are hosted on **App Platform** as separate components.
- **Use environment variables for API URLs and deployment-specific configuration.** With Vite, that means `VITE_`-prefixed vars read via `import.meta.env`:
  - `VITE_API_BASE_URL` — e.g. `http://localhost:8000` in dev, the deployed backend URL in production.
- **Do not hardcode localhost URLs into production code.** Provide a committed `.env.example` for the frontend and keep real values out of the repo.
- Remember to add the deployed frontend origin to the backend's `CORS_ORIGINS` — a correct frontend still fails without it.
- Uploaded images are served by the **backend** at `/uploads/...`; on App Platform the `data/` and `uploads/` directories must be persistent volumes or the images vanish on restart.

## 8. Working style

Work in orchestra mode (§3): the conductor inspects, plans, and verifies; Sonnet subagents write the code. Before any of it, inspect the existing repository and the finished design (§2) carefully. Preserve the current architecture and styling conventions.

**Do not ask unnecessary questions.** If something small is unspecified, inspect the codebase, make the most reasonable MVP decision, state the assumption in the spec, and continue.
