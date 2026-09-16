# Okteto Manifest field & best-practice reference

Full syntax and worked examples for the `okteto-manifest-optimizer` skill. Every rule here is verified against Okteto's [Optimize your Okteto Development Environment](https://www.okteto.com/docs/tutorials/optimize-your-development-environment/) tutorial and the [Okteto Manifest reference](https://www.okteto.com/docs/reference/okteto-manifest/). Section numbers 1–14 match the tutorial.

## Best practices with examples

### Images & build

**1. Pin images instead of using `latest`.** `latest` forces Kubernetes to pull on every start and prevents node cache reuse.

```yaml
# Bad
image: registry/redis:latest

# Good
image: registry/redis:8.2.1
# or
image: registry/redis@sha256:2678c...
```

**2. Use Okteto Smart Builds.** Okteto tracks builds at the commit and configuration level; if a teammate already built an identical image, the build is skipped from cache. It is enabled by default in most git repositories. You keep it effective by ordering layers well (practice 3) and not copying churny files into early layers (practice 4).

**3. Order Dockerfile lines by update frequency.** Rarely-changed instructions first, frequently-changed last, to maximize layer caching.

```dockerfile
# Rarely changes
FROM node:20-alpine
RUN apk add --no-cache bash

# Changes occasionally
COPY package.json package-lock.json ./
RUN npm install

# Changes frequently
COPY src/ ./src
```

**4. Avoid `COPY . .`.** Copying everything invalidates the cache whenever any file changes. Copy only what a stage needs.

```dockerfile
# Bad
COPY . .

# Good
COPY package.json .
COPY src/ src/
```

**5. Avoid recursive operations.** A recursive `chown` rewrites every file into a new layer; do it at copy time instead.

```dockerfile
# Bad
RUN chown -R user:group /app/dist

# Good
COPY --from=build --chown=user:group /app/dist /app/dist
```

**6. Use BuildKit cache mounts.** Persist build and dependency caches between runs so packages and compiled artifacts are reused.

```dockerfile
FROM golang:1.24
WORKDIR /app
COPY go.mod .
COPY go.sum .
RUN go mod download
COPY main.go main.go
RUN --mount=type=cache,sharing=private,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -o /usr/src/api
```

Common cache targets: Node.js `node_modules` / npm / yarn caches; Java `/root/.m2`; Go `/root/.cache/go-build`.

### Context & sync management (highest impact)

**7. `.dockerignore` — limit the build context.** Exclude everything, then include only build inputs. Docker applies the *last* matching rule, so `*` goes first and the `!` includes follow. For multi-Dockerfile setups you can use image-specific files (e.g. `dev-dockerfile.dockerignore`).

```gitignore
# .dockerignore
# exclude everything by default
*

# only send these as part of the build context
!Dockerfile
!okteto.yml
!docker-compose.yml
!package.json
!src/**
```

**8. `.oktetoignore` — control deployment/test context.** Uses `.dockerignore` syntax. Patterns outside a section apply to every remote command; `[deploy]`, `[destroy]`, `[test]`, and `[test.<name>]` sections scope patterns to one command.

```gitignore
# .oktetoignore
# exclude everything by default
*

# only send these as part of the deploy context
[deploy]
!helm/**
!k8s/**

# only send these as part of the test context
[test]
!tests/**
```

**9. `.stignore` — control file synchronization.** Sync only the files needed for active development; never sync generated artifacts, dependency directories, or VCS metadata. `.stignore` is a Syncthing ignore file: the **first** matching pattern decides, so `!` includes must come *before* the catch-all `*` — the reverse of `.dockerignore`. With `*` first, nothing syncs.

```gitignore
# .stignore
# keep the active source (includes go FIRST -- first match wins)
!src/**
!public/**

# ignore everything else
*
```

When you'd rather list exclusions than includes, name the directories instead of using `*`:

```gitignore
# .stignore
node_modules
dist
.git
```

**10. Precopy sync content into the dev image.** With a multi-stage Dockerfile, build a `-dev` image whose stage already contains the source. This warms build caches and speeds the initial sync.

```dockerfile
FROM golang:1.21 as builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY main.go main.go
RUN go build -o myapp

FROM alpine as production
WORKDIR /app
COPY --from=builder /app/myapp .
```

```yaml
build:
  myapp:
    context: .
    target: production
  myapp-dev:
    context: .
    target: builder

dev:
  myapp:
    image: ${OKTETO_BUILD_MYAPP_DEV_IMAGE}
```

### Data & environment management

**11. Replace DB seed scripts with Volume Snapshots.** Preload databases from an Okteto Volume Snapshot instead of running slow, error-prone seed scripts. Faster and more production-like.

**12. Leverage Okteto Divert.** When a use case doesn't require a fully isolated environment, Divert routes traffic from a shared environment into your dev container — saving resources while staying close to production.

### Development

**13. Use volumes for dev containers.** Persist dependencies and caches across `okteto up` sessions so they aren't re-downloaded or rebuilt each start.

```yaml
dev:
  app:
    volumes:
      - /usr/src/app/node_modules
      - /root/.m2
      - /root/.cache/go-build
```

**14. Use caches for Okteto Test.** Persist dependency and build directories across test runs.

```yaml
test:
  unit:
    image: node:22
    caches:
      - /usr/src/app/node_modules
      - /usr/src/app/downloaded_assets
    commands:
      - npm install
      - npm test
```

## Dev-container correctness (Okteto Manifest reference)

These are not in the optimization tutorial but are required for a correct, fast dev container.

**`resources` (object, optional).** `requests` and `limits` are unset by default. Always set both — unset requests starve the scheduler and cause slow or `Pending` starts.

```yaml
dev:
  api:
    resources:
      requests:
        cpu: "250m"
        memory: "256Mi"
      limits:
        cpu: "1"
        memory: "1Gi"
```

**`forward` ([string], optional) — `localPort:remotePort`.** Reach a container port from `localhost`. Also supports `localPort:remoteService:remotePort` to reach another service in the namespace.

```yaml
forward:
  - 8080:80          # localhost:8080 -> container port 80
  - 5432:postgres:5432
```

**`reverse` ([string], optional) — `remotePort:localPort`.** Send from the container back to your machine (e.g. a debugger callback or log shipping).

```yaml
reverse:
  - 9000:9001        # container 0.0.0.0:9000 -> localhost:9001
```

Forward and reverse use opposite orderings — this is the single most common manifest mistake.

## Manifest field reference

### `build.<name>`

| Field | Notes |
|---|---|
| `context` | Build context directory (e.g. `./api`) |
| `dockerfile` | Dockerfile path relative to `context` |
| `target` | Stage to build; use a second `-dev` entry with `target: builder` for precopy (practice 10) |
| `image` | Optional explicit tag; otherwise Okteto names and pushes it to the Okteto Registry |

Each build named `<name>` exposes `${OKTETO_BUILD_<NAME>_IMAGE}` for use in `deploy` and `dev` (uppercase, `-` → `_`).

### `deploy`

A list of commands or a Helm/manifest deployment. Wire built images through the environment variables:

```yaml
deploy:
  - name: Deploy chart
    command: helm upgrade --install movies chart --set api.image=${OKTETO_BUILD_API_IMAGE}
```

### `dev.<svc>`

| Field | Type | Notes |
|---|---|---|
| `image` | string | Dev-container image; wire to a build with `${OKTETO_BUILD_<NAME>_IMAGE}` |
| `command` | string | Startup command inside the dev container |
| `sync` | [string], required | `localPath:remotePath` (e.g. `.:/code`); pair with `.stignore` |
| `forward` | [string] | `localPort:remotePort` |
| `reverse` | [string] | `remotePort:localPort` |
| `volumes` | [string] | Persist dependency/cache dirs across sessions |
| `resources` | object | `requests` and `limits` — always set both |

### `test.<name>`

| Field | Type | Notes |
|---|---|---|
| `image` | string | Base image for the test container; pin it |
| `commands` | [string], required | Each must exit 0 for the test to pass |
| `caches` | [string] | Cache mounts for dependency/build dirs across runs |
| `artifacts` | [string] | Files/folders exported after the run (coverage, reports) |
| `context` | string | Root for the test run; defaults to the manifest location |
| `depends_on` | [string] | Other test containers to run first |

## Per-language dependency & cache directories

Persist these in `dev.<svc>.volumes` and `test.<name>.caches`, and mount them as BuildKit caches in the Dockerfile.

| Stack | Directories |
|---|---|
| Node.js | `node_modules`, `~/.npm` (or `.yarn/cache`) |
| Go | `/go/pkg/mod`, `/root/.cache/go-build` |
| Java / Maven | `/root/.m2` |
| Java / Gradle | `/root/.gradle/caches` |
| Python | `~/.cache/pip`, the virtualenv (`.venv`) |
| Ruby | the bundle path (e.g. `vendor/bundle`) |

## Worked example: an optimized manifest

A Node service with a multi-stage Dockerfile, precopied dev image, scoped sync, persisted dependencies, resources, and a cached test container.

```yaml
build:
  web:
    context: .
    target: production
  web-dev:
    context: .
    target: builder

deploy:
  - name: Deploy chart
    command: helm upgrade --install web chart --set image=${OKTETO_BUILD_WEB_IMAGE}

dev:
  web:
    image: ${OKTETO_BUILD_WEB_DEV_IMAGE}
    command: npm run dev
    sync:
      - .:/usr/src/app
    forward:
      - 3000:3000
    reverse:
      - 9229:9229
    volumes:
      - /usr/src/app/node_modules
      - /root/.npm
    resources:
      requests:
        cpu: "250m"
        memory: "256Mi"
      limits:
        cpu: "1"
        memory: "1Gi"

test:
  unit:
    image: node:22-alpine
    caches:
      - /usr/src/app/node_modules
      - /root/.npm
    commands:
      - npm ci
      - npm test
```

Ship it with a `.dockerignore` (practice 7) and a `.stignore` (practice 9); add a `.oktetoignore` (practice 8) if the deploy or test context is large. Then run `okteto validate`, and rebuild and redeploy (`okteto build`, `okteto deploy --wait`): a changed manifest, Dockerfile, or `.dockerignore` is a build input and does not sync.
