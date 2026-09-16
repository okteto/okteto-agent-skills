---
name: okteto-onboarding
description: |
  Use when a project has NO okteto.yaml/okteto.yml and the user wants it on
  Okteto — e.g. "get this repo onto Okteto", "set up a dev environment for
  this", "create an Okteto manifest", "onboard this service". Also use when
  okteto deploy fails because no manifest exists. Do NOT use if okteto.yaml
  or okteto.yml already exists — that is the okteto skill's domain.
license: Apache-2.0
---

# Okteto Onboarding Skill

## 1. Activation

This skill activates when **all** of the following are true:
- The project has **no** `okteto.yaml` or `okteto.yml` at the repo root
- The user is asking about Okteto, dev environments, or onboarding (e.g., "how do I get this onto Okteto", "set this repo up for Okteto", "create an Okteto manifest")

**Do NOT activate if:**
- An `okteto.yaml` or `okteto.yml` already exists at the repo root — that is the existing `okteto` skill's domain. Defer to it.
- The user is asking how to *use* Okteto with an existing manifest. Defer to the existing `okteto` skill.

**Pre-flight check.** Before starting Phase 1, run:

```bash
ls okteto.yaml okteto.yml 2>/dev/null
```

If anything is returned, stop and tell the user:
> "I see `okteto.yaml` already exists. The `okteto-onboarding` skill is for repos *without* a manifest. For working with the existing manifest, use the `okteto` skill or run `/dev-setup`."

**Two operating modes:** collaborative (default — user is in the loop) and autonomous (no human; opens a PR). See Section 7. Most of the workflow is mode-agnostic; only Phase 6 and the resolution of "ask the user" branches differ.

## 2. Phase 1 — Discover

Build an internal model of the repo: services, their build contexts, ports, dev commands, and any existing deploy artifacts. Read signals in priority order. **Do not write the manifest yet.**

### 2.1 Signal priority

1. **`docker-compose.yml` / `compose.yaml`** — the richest signal for services and dev, and a valid `deploy:` source on its own. If present, it is the primary blueprint for `build:` and `dev:`, and Okteto can deploy it directly via `deploy: compose:` (Section 4.1) — no chart or k8s manifests required. See the mapping table below.
2. **Existing Helm chart** — any `Chart.yaml` under `chart/`, `charts/`, `helm/`, or `deploy/`. If found, `deploy:` will be a `helm upgrade --install` command. **Do not generate or modify the chart.**
3. **Existing k8s manifests** — `.yaml` files with `kind:` headers under `k8s/`, `manifests/`, `deploy/` — but **excluding any `templates/` subdirectory** (those belong to a Helm chart and are not directly applyable). If found, `deploy:` will be `kubectl apply -f ...`. **Do not author these manifests.**
4. **Per-service Dockerfiles** — for repos without compose, each top-level `Dockerfile` is a candidate service. Service name comes from the parent directory.
5. **Language manifests** — `package.json`, `go.mod`, `pom.xml`, `pyproject.toml`, `Gemfile`, `Cargo.toml`. Used to pick the dev image and infer the dev command. When this is the only signal (no Dockerfile, no compose), name the service after the project's `name` field (e.g., `pyproject.toml`'s `[project] name`, `package.json`'s `name`) or, failing that, the repo directory.
6. **Procfile / Makefile** — secondary signals when language manifests are ambiguous.

**These signals are complementary, not exclusive.** A repo can carry more than one. Common combinations:

- **Compose only** — compose drives `build:`, `dev:`, *and* `deploy:` (via `deploy: compose:`). Enough to reach Level 2 with no chart or k8s manifests.
- **Chart or k8s only** — the artifact drives `deploy:`; derive `dev:` from the deployed workload names (Phase 3, bullet 4).
- **Compose *and* a chart/k8s** — the deploy source is ambiguous. Compose files are often the dev path and charts the prod path, but not always. **Do not assume the chart wins `deploy:`.** Ask the user which should drive it — compose, the chart/manifests, or both combined (Section 2.5).

Apply each signal to its own section of the manifest rather than treating priority order as a winner-takes-all.

**Don't stop at the root compose file.** Real projects routinely ship several: a base or production compose (often at the repo root, using published `image:`s) plus one or more development composes under `docker/`, `dev/`, or named `*.dev.yml` / `compose.dev.yml`. Glob for `**/docker-compose*.y*ml` and `**/compose*.y*ml` (skip `node_modules`, vendor, and build dirs) — not just `./docker-compose.yml`. The split usually maps cleanly:

- The **dev** compose — the one that **builds from source** (`build:` with `context:`/`target:`, plus source bind mounts) — drives `build:` and `dev:`.
- A **base / production / `*.preview*`** compose can drive `deploy:`.

When more than one compose file exists, **list them and ask** which describes development and which is the deploy source (Section 2.5). **Do not assume the root file is the dev blueprint** — a root compose built entirely from published images is a *run/deploy* file, and developing against a published image is meaningless.

**Follow `include:` and resolve anchors.** A compose file may pull in others via `include:` (or the older `extends:`) — read those too, or you'll miss services. Parse the *resolved* YAML, not raw lines: dev composes commonly rely on anchors and `x-` extension fields (`build: *some-anchor`, `<<: *some-env`), which only make sense after expansion.

**An existing Okteto-aware compose is a strong signal.** If a compose file already uses Okteto Compose extensions (`endpoints:`, `public:`) or is clearly an okteto deploy file, prefer it as the `deploy:` source and surface it to the user rather than authoring something new — the customer has already expressed how they want to deploy.

### 2.2 Compose → Okteto mapping

When `docker-compose.yml` is present, map fields like this:

| Compose field | Okteto manifest field |
|---|---|
| `services.<name>` | `build.<name>` (when there's a `build:` block) and `dev.<name>` |
| `build.context`, `build.dockerfile` | `build.<name>.context`, `build.<name>.dockerfile` |
| `image` (no `build`) | `dev.<name>.image` directly — **do not** add a `build.<name>` entry for pre-built images |
| `ports` (Level 1) | `dev.<name>.forward` — preserves the user's local-port intent |
| `ports` (Level 2+) | exposed via the `deploy:` source (compose `deploy:`, Helm, or k8s); also keep `dev.<name>.forward` for active dev sessions |
| `command` | starting point for `dev.<name>.command` |
| `volumes` (host bind mounts only) | `dev.<name>.sync` candidates |
| `depends_on` | ordering hint for the deploy step |
| `environment` | `dev.<name>.environment` |

Ignore compose-only concepts that don't translate (`networks`, `restart`, named volumes, `extends`).

**Backing services vs. dev targets.** A compose service that uses a published `image:` with no `build:` and no source in the repo (databases, caches, object stores, mail catchers, message brokers — `postgres`, `redis`, `minio`, `nats`, `mailpit`, and the like) is *infrastructure*: include it in the `deploy:` stack, but it rarely belongs in `dev:`. Reserve `dev:` for the services you actually edit — the ones that build from source in the repo. **Don't create a `dev:` entry for every compose service by default**; a repo with ten compose services often has only one or two real dev targets.

### 2.3 Dev-image picks by language manifest

Pick the image **family** from the language manifest, and the **tag from the version the repo declares** — do not hard-code a version. Reading the declared version keeps the pick current instead of freezing a minor that goes stale.

| Language manifest | Image family | Where to read the version |
|---|---|---|
| `package.json` | `okteto/node` | `engines.node` |
| `go.mod` | `okteto/golang` | the `go 1.x` line |
| `pom.xml` / `build.gradle*` | `okteto/maven` or `okteto/gradle` | `maven.compiler.release` / `sourceCompatibility`, or the wrapper version |
| `pyproject.toml` / `requirements.txt` | `okteto/python` | `requires-python` or `.python-version` |
| `Gemfile` | `okteto/ruby` | `.ruby-version` or the `ruby` directive |
| `Cargo.toml` | `okteto/rust` | `rust-version` (MSRV), if set |

Tag the image with the declared version, e.g. `okteto/golang:1.23` when `go.mod` says `go 1.23`. **State the source in an inline comment** (`# go.mod declares Go 1.23`).

**When the repo declares no version**, do not invent a specific minor — it will be wrong as often as right. In collaborative mode, ask the user which version they target. In autonomous mode, pin to the family's current stable major and flag it in the PR as a decision to confirm (`# go.mod has no version line — defaulting to a recent stable; confirm`).

### 2.4 Dev-command picks

| Signal | Dev command default |
|---|---|
| `package.json` with `scripts.dev` | `npm run dev` |
| `package.json` with `scripts.start` (no dev) | `npm start` |
| `go.mod` | `bash` (Go projects usually want a shell to `go run` manually) |
| `pom.xml` with `spring-boot-maven-plugin` | `mvn spring-boot:run` |
| `pyproject.toml` with FastAPI/Flask | `bash` (varies too much to default) |
| Procfile with a `web:` line | the value of `web:` |
| compose `entrypoint`/`command` is `sleep infinity` or `tail -f /dev/null` | `bash` — this is a **dev-container placeholder** (the container stays alive so you exec in), not a real command. Don't copy it into `dev.<svc>.command`; it's exactly the pattern Okteto's `dev:` replaces. |
| None of the above | `bash` |

### 2.5 When discovery is ambiguous

If discovery leaves real ambiguity, **ask one targeted question at a time** rather than guessing. Examples:

- "I see Dockerfiles in `api/` and `web/` but no compose file. Should both be services?"
- "I found a Helm chart at `chart/` and another at `infra/helm/`. Which one is the canonical deploy?"
- "This repo has both a `docker-compose.yml` and a Helm chart. Which should drive `deploy:` — the compose file, the chart, or both? (Compose is often the dev path and the chart the prod path, but I don't want to assume.)"
- "I see several compose files — `docker-compose.yml` at the root and `docker/docker-compose.dev.yml`. Which one describes how you *develop* (builds from source), and which should I use to *deploy* the stack?"
- "Your `package.json` doesn't have a `scripts.dev` — what command starts your dev server?"

Do **not** ask the user about everything. Only ask when a guess would be likely wrong. Trust the signals.

**In autonomous mode, do not ask.** Pick the most conservative interpretation, proceed, and note the ambiguity in the PR description (Section 7.2 covers this).

### 2.6 Output of Phase 1

Internally, you should now have a model like:

```
Services: [api, web, worker]
api:    Dockerfile @ ./api,    port 8080, dev cmd `bash`,        dev image `okteto/golang:1.22`
web:    Dockerfile @ ./web,    port 3000, dev cmd `npm run dev`, dev image `okteto/node:20`
worker: Dockerfile @ ./worker, no port,   dev cmd `bash`,        dev image `okteto/python:3.12`
Deploy: helm chart at ./chart
Tests: detected `go test ./...` in api, `npm test` in web
```

Show this summary to the user before moving to Phase 2.

## 3. Phase 2 — Negotiate scope

Before drafting, frame the choice and pick a level on the adaptive ladder.

### 3.1 The framing block (always show this to the user)

> *In Okteto, `deploy:` describes how to **provision** the environment — from a Docker Compose file, a Helm chart, or k8s manifests. `dev:` describes how to **live-edit** a running service — file sync, the dev image, the startup command. You can use Okteto with just `dev:` if you already have a way to deploy your stack, or have Okteto handle both.*

This same framing goes at the top of the generated `okteto.yaml` as a header comment.

### 3.2 The adaptive ladder

| Level | What it produces | Requires |
|---|---|---|
| **1 — dev-only** | `dev:` section only. User runs their own deploy externally. | Nothing extra. |
| **2 — deploy + dev** | `build:` + `deploy:` + `dev:`. `okteto deploy` brings up the stack. | A Helm chart, k8s manifests, **or a Docker Compose file** in the repo. |
| **3 — full lifecycle** | Adds `test:` containers wired to existing test commands. | Level 2 prereqs PLUS detected tests. |

### 3.3 Recommendation logic

Recommend a level based on what Phase 1 found:

A **deploy source** is a Helm chart, k8s manifests, or a deployable Docker Compose file.

- A deploy source found AND tests detected → recommend **Level 3**
- A deploy source found, no tests → recommend **Level 2**
- No deploy source at all (no chart, no k8s manifests, no compose) → recommend **Level 1** (and explain why higher levels are unavailable)

When more than one deploy source exists (e.g. compose *and* a chart), confirm which one drives `deploy:` (Section 2.5) before drafting — don't default to the chart.

Then ask the user (collaborative mode) or accept the recommendation (autonomous mode):

> "Based on what I found, I'd recommend Level [N]. Want to go with that, pick a different level, or have me explain the trade-offs?"

### 3.4 Locking the level

Once chosen, the level is **locked for the rest of the session.** Do not negotiate level mid-flight. If the draft turns out to need a different level (e.g., the chart is broken), surface that as a Phase 5 failure and re-enter Phase 2 cleanly.

## 4. Phases 3–4 — Draft and refine

### 4.1 Draft (Phase 3)

Write `okteto.yaml` to the repo root. The user must see the **actual file**, not just a summary.

**Required content of every draft:**

1. **Header comment block** — the framing from Section 3.1, plus a note that the file was generated by `okteto-onboarding` and the user is expected to edit it. Include the chosen scope level and a one-line rationale.
2. **`build:` section** (Level 2+) — one entry per service with `context` and `dockerfile`. Skip pre-built images here (they go directly under `dev.<svc>.image`).
3. **`deploy:` section** (Level 2+) — points at the chosen deploy source:
   - **Compose:** `deploy: { compose: docker-compose.yml }` (optionally a `services:` subset). The simplest path when the repo has no chart or manifests.
   - **Helm:** a `helm upgrade --install` command, passing built images via `--set ...=${OKTETO_BUILD_<SERVICE>_IMAGE}` (see "Wiring built images" below).
   - **k8s manifests:** a `kubectl apply -f ...` command.

   See the schema examples below.
4. **`dev:` section** (always) — one entry per service the user wants in dev mode, with `image`, `command`, and `sync`. The **key name** must match the workload Okteto will deploy:
   - **Compose repo:** the compose service name (mapping table, Section 2.2).
   - **Helm/k8s repo (no compose):** the name of the Kubernetes workload the chart/manifests create — the `Deployment`/`StatefulSet` `metadata.name` (render the chart or read the manifest to find it). A `dev:` key matching no deployed workload won't attach.

   The `image`, `command`, and `sync` come from the Dockerfile + language manifest (Sections 2.3–2.4) regardless of repo shape.
5. **`test:` section** (Level 3) — one entry per detected test command. See the schema example below.

**Sync-path defaults:**
- **Single-service repo** (one Dockerfile or one language manifest at the root): `.:/usr/src/app` is a reasonable default. If the Dockerfile sets `WORKDIR`, use that path on the right side instead of `/usr/src/app`.
- **Multi-service repo** (per-service Dockerfiles or compose with multiple services): scope each service's sync to its own subdirectory, e.g., `./api:/usr/src/app`. Syncing the whole repo into every container is almost always wrong.

**Inline comments are required on every non-obvious choice** (image picks, command picks, sync paths, `forward:` ports). Image and command picks are non-obvious by default — comment them.

**Wiring built images into `deploy:` and `dev:`.** Images defined under `build:` are pushed to the Okteto Registry and exposed to the rest of the manifest as environment variables:

- `OKTETO_BUILD_<SERVICE>_IMAGE` — full image reference (the one you almost always want)
- `OKTETO_BUILD_<SERVICE>_REGISTRY`, `_REPOSITORY`, `_SHA` — the parts, if you need them

`<SERVICE>` is the `build:` key uppercased, with `-` replaced by `_` (so `build.web-api` → `OKTETO_BUILD_WEB_API_IMAGE`). Use these so the deployed workload runs the freshly built image instead of a stale or hard-coded one:

- **Helm:** `--set api.image=${OKTETO_BUILD_API_IMAGE}`
- **k8s manifests:** substitute the value (e.g. `envsubst`) before `kubectl apply`, or template the image field.
- **Compose:** the `build:` section already overrides the matching compose `image:` by service name — no `--set` needed.
- **`dev:`:** set `dev.<svc>.image: ${OKTETO_BUILD_<SVC>_IMAGE}` when the user wants to develop against the built application image rather than a generic toolchain image (Section 2.3).

**Example: Level 2/3 fragment (build + deploy + dev + test)**

```yaml
build:
  api:
    context: ./api
    dockerfile: Dockerfile  # using the existing Dockerfile

deploy:
  - name: Deploy chart
    command: helm upgrade --install myapp ./chart --set api.image=${OKTETO_BUILD_API_IMAGE}  # built api image wired in

dev:
  api:
    image: okteto/golang:1.23  # tag from api/go.mod (go 1.23)
    command: bash               # Go services usually want a shell to `go run` manually
    sync:
      - ./api:/usr/src/app      # per-service sync; tighten if you have large generated dirs

test:
  api:
    image: okteto/golang:1.23
    context: ./api
    commands:
      - go test ./...           # detected from the project's test layout
```

**Example: Level 2 fragment (compose-driven deploy, no chart)**

```yaml
build:
  api:
    context: ./api
    dockerfile: Dockerfile

deploy:
  compose: docker-compose.yml   # deploy the stack straight from compose — no chart or k8s manifests needed

dev:
  api:
    image: okteto/golang:1.23   # tag from api/go.mod (go 1.23)
    command: bash
    sync:
      - ./api:/usr/src/app
```

**Compose-as-deploy caveats.** A compose file written for local development often won't deploy cleanly to a cluster as-is. Before committing to `deploy: compose:`, scan the compose file and warn the user about:

- **Host-IP port bindings** (e.g. `127.0.0.1:9229:9229`) — Okteto's compose deploy rejects them (`Host IP is not allowed`). Drop the host-IP prefix (`9229:9229`).
- **Source bind-mount volumes** (e.g. `./api:/usr/local/app`) — on a cluster these become *empty* volumes that **shadow the image's application code**, so the service crashes (`can't open file 'app.py'`). They belong in `dev.<svc>.sync`, not in a deployed compose.

If the compose file leans on these dev-only constructs, surface it up front — don't discover it at deploy time. In preference order:

1. **Generate a deploy-ready compose** — derive a `compose.okteto.yaml` from the original with the cluster-hostile parts removed, and point `deploy: compose: compose.okteto.yaml` at it. See "Generating a deploy-ready compose" below.
2. **Reuse an existing deploy compose** — if the repo already ships one (e.g. a `*.preview*` or production compose without the dev volumes/ports), point `deploy: compose:` at that.
3. **Use the chart/k8s manifests** for `deploy:` instead, if the repo has them. This is why a repo with *both* compose and a chart often wants the chart for `deploy:` even though compose drives `dev:` (Section 2.5).

**Generating a deploy-ready compose (`compose.okteto.yaml`).** When compose is the chosen deploy source but the file carries dev-only constructs, write a *derived copy* rather than editing the user's original. This is a mechanical transform of the user's own file — not a hand-authored deploy artifact — so show it to the user as a diff against the source. Reference it explicitly: `deploy: { compose: compose.okteto.yaml }`. Apply these transforms:

- **Drop host-IP port prefixes** — `127.0.0.1:9229:9229` → `9229:9229`. Debug-only ports (inspectors) can be removed entirely; they belong in `dev.<svc>.forward`.
- **Remove source bind-mount volumes** — `./src:/app` and the like. The image already contains the code; these belong in `dev.<svc>.sync`. Keep named/data volumes (e.g. `db-data`).
- **Replace dev-container placeholders** — a service whose `entrypoint`/`command` is `sleep infinity` won't run the app when deployed. Restore its real start command (from the Dockerfile `CMD` or a production compose), or drop the override.

Two things the transform **cannot** silently fix — flag these to the user rather than pretending the result is clean:

- **Host-path config/script mounts** (e.g. an init script mounted as the container's entrypoint) — removing the mount doesn't make the service work; the file has to be baked into an image. Leave it and warn.
- Anything else service-specific the scan can't reason about.

Add a header comment to `compose.okteto.yaml`: that it was derived from `<original>` by the skill, what changed, and that it's safe to edit or regenerate. **The generated file is best-effort** — still climb the Phase 5 ladder (validate → build → deploy) to confirm the stack actually comes up.

**Example: Level 1 fragment (dev-only, single service)**

```yaml
dev:
  myapp:                        # service name from pyproject.toml [project] name
    image: okteto/python:3.12   # pyproject.toml declares requires-python >=3.12
    command: bash               # no FastAPI/Flask signal — shell is the safe default
    sync:
      - .:/usr/src/app          # full-repo sync; exclude .venv, __pycache__ if they grow
```

**Performance comes after the first successful deploy.** The draft above is deliberately plain. Once it validates and deploys, the `okteto-manifest-optimizer` skill tightens it — scoped `.stignore`/`.dockerignore`, dependency directories in `volumes`, `resources`, `test.caches`. Get a working manifest first; do not fold those in here.

### 4.2 Refine (Phase 4)

Show the file to the user. In collaborative mode, ask:

> "Here's the draft. Want me to change anything before we validate? Common edits: adjust sync paths to exclude `node_modules`/`vendor`/`target`, change the dev image version, add an env var, or swap the deploy command."

Common edit patterns:

| User says | Edit |
|---|---|
| "exclude `node_modules`" | Change `sync` to a list with `!node_modules` ignore patterns or use a more specific path |
| "use Go 1.21 instead" | Update `image:` to `okteto/golang:1.21` |
| "I need this env var" | Add to `dev.<svc>.environment:` |
| "use my values file" | Update `deploy:` helm command with `-f values.staging.yaml` |

**Iteration is cheap — keep editing until the user is satisfied.** Do not move to Phase 5 until they say "looks good" or equivalent.

In autonomous mode, skip the ask and move directly to Phase 5. Edits will be requested via the PR review.

## 5. Phase 5 — Validate (tiered)

Climb the validation ladder as far as the environment supports. Tier 1 is mandatory; Tiers 2 and 3 are opt-in.

### 5.1 Tier 1 — `okteto validate` (always)

Run:
```bash
okteto validate
```

**What it catches:** YAML syntax, schema violations, missing required fields.
**What it does NOT catch:** wrong sync paths, missing services in `deploy:`, broken Helm refs, images that fail to build.

If it fails, treat as a Phase 4 issue and fix before continuing.

The skill **does not finish without Tier 1 passing.**

### 5.2 Tier 2 — `okteto build` (offered if Dockerfiles or `build:` exist)

Pre-check: run `okteto context show`. If it errors or returns no context, **skip Tier 2** and inform the user:

> "Skipping the build check — no Okteto context. The manifest is syntactically valid but I haven't proven the Dockerfiles build."

Otherwise, ask:

> "I can run `okteto build` to prove every Dockerfile resolves and pushes. This takes a few minutes per service. Skip / build one service / build all?"

Default to **build all**. If the user has many services (≥ 4) and is in a hurry, offer narrowing.

Run:
```bash
okteto build
```
or
```bash
okteto build <service>
```

### 5.3 Tier 3 — `okteto deploy --wait` (offered if Tier 2 passed and user has a context)

Note: there is **no `okteto deploy --dry-run`** flag. Full deploy is the only Tier 3 option.

Ask:

> "I can do a full deploy to verify the manifest works end-to-end. This will create resources in your namespace `<ns>`. After it succeeds, I'll show you the endpoints. You can `okteto destroy` after if you want. Proceed?"

Run:
```bash
okteto deploy --wait
okteto endpoints
```

**On success:** print endpoints. **Do not** run `okteto destroy` automatically — that's the user's call.

### 5.4 On failure at any tier

1. **Surface the raw CLI error verbatim.** Do not paraphrase.
2. **Diagnose the likely cause** based on the manifest section involved (e.g., a Helm error → `deploy:`; a build error → `build:` or the Dockerfile).
3. **Propose a concrete edit to the manifest.** Show the diff, not "you should change X."
4. After the user approves the fix:
   - If the edit changed manifest **structure** (added/removed/renamed sections, changed YAML shape), re-run **Tier 1** first to catch new schema problems, then re-run the failing tier.
   - If the edit was purely a value change (image version, sync path, env var), re-run **only the failing tier**.

### 5.5 Final summary

Once the ladder is climbed (or stopped), summarize:

> "✅ `okteto validate` passed
> ✅ `okteto build` passed for all services
> ⏭️ `okteto deploy` skipped (you opted out)
> Next: run `/dev-setup` or invoke the `okteto` skill to deploy and start developing."

If tiers were skipped due to environment (no context), say so:

> "⚠️ Skipped Tiers 2 and 3 (no Okteto context). The manifest is syntactically valid but not deploy-tested."

## 6. Phase 6 — Handoff or PR

### 6.1 Collaborative mode: handoff

Point the user at the next step:

> "The manifest is in place. To bring up your environment, you can:
> - Run `/dev-setup` for a guided deploy + dev mode
> - Or invoke the `okteto` skill in any future session — it'll pick up the manifest you just created
>
> If you change the manifest, re-run `okteto validate` (or come back to me)."

State which validation tiers were run and which were skipped (see Section 5.5).

**Do NOT delete the manifest, run `okteto destroy`, or push to a remote.** The work product is the file on disk.

### 6.2 Autonomous mode: PR

Create a branch, commit the manifest, push, and open a PR. The PR is the human review gate.

**Before running the commands below, substitute every `<placeholder>` with a real value from your Phase 1 / Phase 5 results.** Do not send literal `<list>`, `<N>`, `<bulleted list of services...>`, etc. to a real PR. For the validation checklist, use `[x]` if the tier passed and `[ ]` if it was skipped or failed.

````bash
git checkout -b okteto/onboarding
git add okteto.yaml
git commit -m "Add Okteto manifest

Generated by okteto-onboarding skill.
Discovered services: <list>
Scope level: <N>
Validation: <tiers passed>"
git push -u origin okteto/onboarding
gh pr create --title "Add Okteto manifest" --body "$(cat <<'EOF'
## Summary
This PR adds an Okteto manifest generated by the `okteto-onboarding` skill.

## Discovered services
<bulleted list of services with their Dockerfiles and dev commands>

## Scope level
Level <N> — <one-sentence rationale>

## Validation
- [<x or space>] `okteto validate` passed
- [<x or space>] `okteto build` ran for all services
- [<x or space>] `okteto deploy --wait` succeeded with endpoints

## Decisions to confirm
- [ ] Dev image picks (e.g., `okteto/golang:1.22`) match your toolchain
- [ ] Sync paths exclude appropriate generated dirs (node_modules, vendor, target)
- [ ] Helm/kubectl deploy command matches your usual workflow

🤖 Generated by the okteto-onboarding skill
EOF
)"
````

The skill **never merges** the PR. A human reviews and merges.

## 7. Operating modes

### 7.1 Collaborative (default)

A user is in the loop. Each phase that needs a decision asks a question. Defaults are presented but not auto-selected.

### 7.2 Autonomous (opt-in)

No human is expected to intervene. Inferred from context the same way the existing `okteto` skill does — for example, when invoked from a CI pipeline or a ticket-driven session.

In autonomous mode:
- **Scope level** → highest level the discovery *supports*. Level 2 requires a deploy source (a chart, k8s manifests, or a deployable compose file); Level 3 additionally requires detected tests. With no deploy source at all, stay at Level 1 even if tests are present. When both compose and a chart exist, pick the most conservative deploy source and note the choice in the PR.
- **Validation tier** → Tier 1 always; Tier 2 if `okteto context show` succeeds; Tier 3 only if the trigger explicitly authorizes a deploy (label, env var, or explicit instruction).
- **Discovery ambiguities** → pick the most conservative interpretation and note it in the PR description.
- **Phase 6** → always opens a PR (Section 6.2), never hands off.

## 8. CLI quick reference

| Command | When | Purpose |
|---|---|---|
| `okteto validate` | Phase 5 Tier 1 (always) | Check manifest syntax/schema |
| `okteto context show` | Phase 5 pre-checks | Verify cluster connection before Tiers 2/3 |
| `okteto build [<service>]` | Phase 5 Tier 2 | Prove Dockerfiles resolve and push |
| `okteto deploy --wait` | Phase 5 Tier 3 | Full end-to-end validation |
| `okteto endpoints` | Phase 5 Tier 3 | Print URLs after a successful deploy |

**Never** run `okteto up` from this skill — it's interactive and belongs to the existing `okteto` skill / the user. **Never** run `okteto destroy` — leave that to the user.

## 9. Common mistakes to avoid

- **Triggering when an `okteto.yaml` already exists.** Always do the pre-flight check from Section 1.
- **Generating a Helm chart or k8s manifests.** This skill does not author deploy artifacts. If the user has no chart, no k8s manifests, *and* no deployable compose file, recommend Level 1 and stop. A compose file alone is enough for Level 2 via `deploy: compose:` — don't drop to Level 1 just because there's no chart. (The one exception is a derived `compose.okteto.yaml` — a mechanical transform of the user's *own* compose, Section 4.1 — never a chart or k8s manifest written from scratch.)
- **Assuming the chart drives `deploy:` when a compose file is also present.** Ask which the user wants (Section 2.5); don't silently pick the chart.
- **Recommending `deploy: compose:` without scanning for dev-only constructs.** Host-IP port bindings and source bind-mount volumes break a cluster deploy (Section 4.1 caveats). Warn the user up front, don't surface it at deploy time.
- **Reading only the root `docker-compose.yml`.** Projects often keep the dev compose under `docker/` or as `*.dev.yml`, separate from a published-images root compose. Glob for all compose files and follow `include:` (Section 2.1). Building `dev:` from a published-images compose produces a useless manifest.
- **Putting every compose service in `dev:`.** Backing services (databases, caches, object stores, brokers) are deploy-only infrastructure. `dev:` is for the services you edit (Section 2.2).
- **Copying a `sleep infinity` entrypoint into `dev.<svc>.command`.** That's a dev-container placeholder, not a real command — use `bash` (Section 2.4).
- **Hard-coding a dev-image version.** Read the version the repo declares (Section 2.3); only fall back to a default when none is declared, and flag the fallback.
- **Forgetting to wire built images downstream.** A `build:` entry isn't enough on its own for Helm/k8s deploys — pass `${OKTETO_BUILD_<SERVICE>_IMAGE}` into the deploy command so the workload runs the image you just built.
- **Skipping the framing block.** The `dev:` vs `deploy:` framing in Section 3.1 must be shown to the user *and* written into the manifest as a header comment.
- **Climbing the validation ladder without checking `okteto context show` first.** Tiers 2 and 3 require a working context.
- **Paraphrasing CLI errors on validation failure.** Show the raw output; the user (or the next agent) needs to see exactly what Okteto said.
- **Asking the user about everything.** Trust the signals from Phase 1. Only ask when discovery is genuinely ambiguous.
- **Merging the PR in autonomous mode.** The PR is the human gate. Never merge.
- **Recommending `okteto/samples/` templates.** Those are demos. Build the manifest from discovered facts, not templates.
