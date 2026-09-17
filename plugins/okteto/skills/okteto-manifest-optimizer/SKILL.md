---
name: okteto-manifest-optimizer
description: |
  Use when a repo already has an okteto.yaml / okteto.yml and the user wants it
  faster or reviewed — "make my okteto.yaml faster", "why is my dev environment
  slow to start or sync", "review this manifest for performance", "tighten the
  build / dev / test sections" — or when authoring the .dockerignore /
  .oktetoignore / .stignore files that go with a manifest. Do NOT use on a repo
  with no manifest yet: service discovery and the first draft belong to
  okteto-onboarding (optimize its draft here afterwards). Do NOT use to debug a
  broken environment (okteto-debugging) or to develop inside one (okteto).
license: Apache-2.0
---

# Okteto Manifest Optimizer

This skill reviews and rewrites Okteto Manifests (`okteto.yaml`) so they follow Okteto's [documented performance best practices](https://www.okteto.com/docs/tutorials/optimize-your-development-environment/), together with the `.dockerignore`, `.oktetoignore`, and `.stignore` files that go with them. Slow environments almost always trace to one of three causes: unpinned images that defeat node cache reuse, a bloated build or sync context, or dependencies that are re-downloaded on every start. This skill removes those.

Full field reference, copy-paste ignore-file templates, and a worked manifest live in [`reference/okteto-manifest-fields.md`](reference/okteto-manifest-fields.md), next to this file. Read it when you need the exact syntax; the rules here are enough to act.

## Operating rules

These rules prevent the mistakes that make environments slow. Apply every one to every manifest you produce.

1. **Verify against the repo — never invent.** Read the Dockerfile(s), the dependency manifest (`package.json`, `go.mod`, `pom.xml`, `requirements.txt`), and the existing `okteto.yaml` first. Every service name, image, sync path, volume, and cache dir must trace to something in the repo.
2. **Pin every image.** Never `:latest` — use a version tag or an `@sha256` digest. When a service has a `build:` entry, wire its dev container to it with `${OKTETO_BUILD_<NAME>_IMAGE}` (uppercase the build name, `-` becomes `_`: build `api` → `${OKTETO_BUILD_API_IMAGE}`, build `web-dev` → `${OKTETO_BUILD_WEB_DEV_IMAGE}`). A dev container on a plain toolchain image (no `build:`) just pins that image.
3. **Context and sync are the highest-impact levers — and the two ignore files read in opposite order.** `.dockerignore`: `*` first, then `!`-include only build inputs (Docker applies the *last* matching rule). `.stignore`: `!`-include the active source first, *then* `*` (Syncthing applies the *first* matching rule; `*` first syncs nothing). Never sync artifacts, dependency directories, or `.git`. Add a `.oktetoignore` when the deploy or test context is large.
4. **Persist dependencies and caches — don't re-fetch them.** Put dependency and build-cache directories in `dev.<svc>.volumes`, mirror them in `test.<name>.caches` for test containers, and use BuildKit cache mounts in the Dockerfile. See the [per-language cache map](#per-language-dependency--cache-directories).
5. **Always set `resources.requests` and `resources.limits`** on dev containers. Both are unset by default, which starves the scheduler and causes slow or `Pending` starts.
6. **Get `forward` vs `reverse` direction right.** `forward` is `localPort:remotePort` (reach a container port from `localhost`). `reverse` is `remotePort:localPort` (send from the container back to your machine, e.g. a debugger callback). Swapping them silently breaks the connection.
7. **Order the Dockerfile by change frequency and never `COPY . .`.** Base image and system packages first, dependency install next, source copy last. Copy only what each stage needs. This is what makes Okteto Smart Builds and layer caching effective.
8. **Validate and rebuild what you changed — without being asked.** `okteto.yaml`, the Dockerfile, and `.dockerignore` are build inputs: nothing syncs them, so the environment is stale until it is rebuilt. As soon as the manifest is written, run `okteto validate` (it works offline). Then rebuild and redeploy the way the `okteto` skill requires — `okteto build <service>` and `okteto deploy --wait` — and report the outcome: endpoints on success, the error and your fix on failure. Never run `okteto up`; it is interactive and would hang.

## Workflow

1. **Discover the stack.** Identify each service, its language/build tool, its Dockerfile, and its source layout from the repo (rule 1). If there is no manifest at all, stop and hand off to `okteto-onboarding`; come back to optimize its draft.
2. **Rewrite `build` → `deploy` → `dev` → `test`.** See [Manifest shape](#manifest-shape). Apply the [best-practice levers](#best-practice-levers) as you write each section.
3. **Write the ignore files** (`.dockerignore`, `.stignore`, and `.oktetoignore` if needed) in the order rule 3 gives. The reference has copy-paste templates.
4. **Run the [pre-return review checklist](#pre-return-review-checklist)**, then `okteto validate`, then rebuild and redeploy (rule 8).

## Manifest shape

| Section | Purpose | Optimization focus |
|---|---|---|
| `build` | Images Okteto builds for each service | Pin bases, order layers, cache mounts, a `target` per stage for a `-dev` image |
| `deploy` | How the stack is provisioned (Helm/manifests/commands) | Wire images with `${OKTETO_BUILD_<NAME>_IMAGE}` |
| `dev.<svc>` | Live-edit config: `image`, `command`, `sync`, `forward`/`reverse`, `volumes`, `resources` | Sync source only; persist deps in `volumes`; set `resources`; correct port direction |
| `test.<name>` | Test containers run via Remote Execution | `caches` for dependency/build dirs; pin `image` |

## Best-practice levers

Fourteen practices from the source doc, grouped. One-line reminders here; full examples in the reference file.

**Images & build**

| # | Practice | Do this |
|---|---|---|
| 1 | Pin images | Version tag or `@sha256`; never `:latest` |
| 2 | Okteto Smart Builds | Let identical builds be skipped from cache; don't defeat it with churny layers |
| 3 | Order layers by change frequency | Base + system packages first, deps next, source last |
| 4 | Avoid `COPY . .` | Copy only build inputs (`COPY package.json .`, then `COPY src/ src/`) |
| 5 | Avoid recursive ops | `RUN chown -R` → `COPY --chown=user:group` |
| 6 | BuildKit cache mounts | `RUN --mount=type=cache,target=<dep-or-build-cache>` |

**Context & sync (highest impact)**

| # | Practice | Do this |
|---|---|---|
| 7 | `.dockerignore` | `*` first, then `!`-include only build inputs (last match wins) |
| 8 | `.oktetoignore` | `.dockerignore` syntax with `[deploy]` / `[test]` sections |
| 9 | `.stignore` | `!`-include active source first, then `*` (first match wins); never artifacts, deps, or `.git` |
| 10 | Precopy source into dev image | Multi-stage: a `-dev` build `target` that already contains the source |

**Data & environment**

| # | Practice | Do this |
|---|---|---|
| 11 | Volume Snapshots over seed scripts | Preload databases from a snapshot instead of slow seed scripts |
| 12 | Okteto Divert | When full isolation isn't required, route into a shared environment |

**Dev container & tests**

| # | Practice | Do this |
|---|---|---|
| 13 | `dev.<svc>.volumes` | Persist dep/cache dirs across `okteto up` sessions |
| 14 | `test.<name>.caches` | Cache dep/build dirs across test runs |

Also enforce, from the Okteto Manifest reference: `resources.requests` **and** `resources.limits` on every dev container, and correct `forward`/`reverse` direction (Operating rules 5–6).

### Per-language dependency & cache directories

Persist these in `dev.<svc>.volumes` and `test.<name>.caches`, and mount them as BuildKit caches (more stacks in the reference):

| Stack | Dependency / cache directories |
|---|---|
| Node.js | `node_modules`, `~/.npm` (or `.yarn/cache`) |
| Go | `/go/pkg/mod`, `/root/.cache/go-build` |
| Java / Maven | `/root/.m2` |
| Python | `~/.cache/pip`, the virtualenv / `.venv` |

## Pre-return review checklist

Do not hand back a manifest until all ten pass. Report each result.

1. **No `:latest`** anywhere in `build` or `dev` images — every image is a version tag or `@sha256` digest.
2. **`dev.<svc>.image` is wired via `${OKTETO_BUILD_<NAME>_IMAGE}`** (not a hardcoded tag) for every service that has a `build:` entry.
3. **`sync` is scoped to source**, and the **`.stignore` excludes** artifacts, dependency directories, and `.git` — with any `!` includes *before* a catch-all `*`.
4. **Dependency/build directories are in `dev.<svc>.volumes`** (see the cache map) so they survive restarts.
5. **`resources.requests` and `resources.limits` are both present** on each dev container.
6. **`forward` (`local:remote`) and `reverse` (`remote:local`) point the right way.**
7. **A `.dockerignore` scopes the build context** — `*` first, then `!`-includes for the build inputs only.
8. **`test.<name>.caches` is set** for every test container (where tests exist).
9. **Dockerfiles are layer-ordered and free of `COPY . .`** and recursive `RUN chown -R`.
10. **`okteto validate` passes** on the result, and the rebuild/redeploy from rule 8 is done or under way.

## Related skills

- **`okteto-onboarding`** — discovers services and drafts a first `okteto.yaml` on a repo that has none. It runs first; this skill optimizes its output once the draft deploys.
- **`okteto`** — deploying, developing, and iterating in a live environment (`okteto build`, `okteto deploy`, `okteto up`, `okteto exec`). Rule 8's rebuild step follows its "when a change needs a rebuild" guidance.
- **`okteto-debugging`** — triaging a broken or unhealthy environment (`CrashLoopBackOff`, `OOMKilled`, stuck sync). Use it when the problem is runtime failure, not manifest performance.
