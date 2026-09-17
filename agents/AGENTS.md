# Okteto Development Environment

This project uses [Okteto](https://www.okteto.com) for cloud development environments. When a developer asks you to make a change, test something, or interact with the running environment, use the instructions below.

## Step 1: Discover the project

Read `okteto.yaml` in the project root. This is the source of truth for:

- **build**: which services have container images
- **deploy**: how services are deployed to the cluster
- **dev**: which services support development mode, their sync paths, and startup commands
- **test**: which test containers are available and their commands

Always derive service names from `okteto.yaml`. Never hardcode them.

## Step 2: Discover how to run commands for each service

Look at the `dev` section of `okteto.yaml` for each service. The `command` field tells you how the service starts inside the dev container:

- `command: bash` — the service needs manual build/start steps; check the service directory for a `Makefile`, `package.json`, `pom.xml`, or `go.mod` to find available commands
- `command: yarn start` or `command: mvn spring-boot:run` — the service auto-starts in dev mode; use the same runner for tests (`yarn test`, `mvn test`, etc.)

When a developer asks you to run tests or build a service and you're not sure what command to use, check these files in the service directory before guessing.

## Step 3: Running commands in the dev environment

When a developer has `okteto up <service>` running in their terminal, use `okteto exec` to run commands inside the dev container:

```
okteto exec -- <command>
```

Examples:
- `okteto exec -- go test ./...`
- `okteto exec -- npm test`
- `okteto exec -- make test`
- `okteto exec -- curl localhost:8080/health`

**Do not use `kubectl exec` or try to open a shell directly into a pod.** `okteto exec` is the correct way to run commands in the development container — it handles cluster authentication, namespace selection, and dev container routing automatically. Direct `kubectl exec` calls will not reach the right container and will confuse the session.

**Read-only `kubectl` and `helm` are fine for diagnostics.** Commands like `kubectl get pods`, `kubectl describe pod`, `kubectl logs <pod> --previous`, `kubectl get events`, and `helm status` only read cluster state and are the right tools for debugging unhealthy pods. The rule is about mutations: never change the cluster with `kubectl apply`/`edit`/`delete` or `helm install`/`upgrade` — all changes go through `okteto deploy`.

## The `okteto up` rule

`okteto up <service>` is **interactive** — it starts a live shell inside the dev container with automatic file sync. You must never run it yourself (not in the terminal, not in the background). It will hang waiting for input.

Instead, tell the developer:

> Run this in your terminal: `okteto up <service>`

If you are isolating a worktree, include the namespace: `okteto up <service> -n <ns>`.

Once they confirm it's running, you can use `okteto exec` freely.

## Worktrees and namespace isolation

An Okteto **namespace** is the unit of isolation. It comes from the active Okteto context (`~/.okteto`), which is **global to the machine** — not per-directory. If you work in a **git worktree** (or any second checkout of the same repo), you share the same `okteto.yaml` as the other worktrees, so deploying into the same namespace makes them collide: the second `okteto deploy` overwrites the first, logs/endpoints get crossed, and `okteto destroy` in one wipes the other.

**Give each worktree its own namespace:**

1. Detect a worktree: `git rev-parse --git-common-dir` differs from `git rev-parse --git-dir`, or check `git worktree list`.
2. Derive a name from the branch (lowercase alphanumeric and `-`, start/end alphanumeric, ≤ 63 chars):
   ```bash
   ns=$(git branch --show-current | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/^-*//; s/-*$//' | cut -c1-50)
   ```
3. Create it once: `okteto namespace create <ns>`.
4. Pass `-n <ns>` on **every** Okteto command (`deploy`, `build`, `logs`, `endpoints`, `test`, `destroy`, and `okteto up` when you hand it to the developer).

**Do not use `okteto namespace use <ns>`** to isolate worktrees — it switches the active namespace in the shared global context and races with other worktrees or agents on the same machine. The `-n` flag is per-invocation and safe under concurrency.

A single primary checkout (not a worktree) can use the context's default namespace — no `-n` needed.

## Common workflows

### Setting up the environment

1. Run `okteto version` to confirm the CLI is installed
2. Run `okteto context show` to confirm the cluster connection
3. Run `okteto deploy --wait` to build images and deploy all services
4. Run `okteto endpoints` to show the live URLs
5. Ask which service the developer wants to work on, then tell them to run `okteto up <service>` in their terminal

### Making a change and testing it in Okteto

1. Read the relevant source files and make the requested change
2. If the developer has `okteto up <service>` running, file changes sync automatically — no rebuild needed for interpreted languages
3. Run `okteto exec -- <test command>` to validate the change in the live container
4. Share the output with the developer

If you're unsure whether `okteto up` is running, ask the developer before using `okteto exec`.

### Rebuilding after a change that requires a new image

For changes that affect compiled binaries, new dependencies, or the Dockerfile itself:

1. `okteto build <service>` — rebuilds and pushes the service image using the Okteto Build Service
2. `okteto deploy --wait` — redeploys with the updated image

Do not build Docker images locally. Use `okteto build` to leverage the remote build service.

### Changing `okteto.yaml`

If you modify `okteto.yaml`, always run `okteto validate` before deploying:

1. `okteto validate` — checks the manifest for syntax and schema errors
2. Fix any errors before continuing
3. `okteto deploy --wait` — deploy with the updated manifest

Never deploy a modified `okteto.yaml` without validating first — a bad manifest will fail mid-deploy and leave the environment in a broken state.

### Checking what's wrong

| Situation | What to do |
|-----------|------------|
| Service not responding | `okteto logs <service>` |
| Pod crashing or stuck (`CrashLoopBackOff`, `OOMKilled`, `Pending`) | `kubectl get pods`, then `kubectl describe pod <pod>` and `kubectl logs <pod> --previous` — read-only kubectl is fine for diagnostics |
| Need to inspect state | `okteto exec -- <diagnostic command>` |
| Tests failing | Read test output, fix code, re-run with `okteto exec` |
| Environment looks stale | `okteto deploy --wait` to redeploy |
| Persistent unexplained failure | `okteto doctor` — generates a diagnostic bundle to share with Okteto support |

## Writing an efficient okteto.yaml

When you create or edit `okteto.yaml`, follow Okteto's manifest performance best practices. Slow environments almost always come from unpinned images, a bloated build or sync context, or dependencies re-fetched on every start:

- **Pin every image** — a version tag or `@sha256`, never `:latest`. When a service has a `build:` entry, wire its dev image to it with `${OKTETO_BUILD_<NAME>_IMAGE}` (uppercase the build name, `-` becomes `_`).
- **Scope the context — the two ignore files read in opposite order.** `.dockerignore`: `*` first, then `!`-include only build inputs (Docker applies the last matching rule). `.stignore`: `!`-include the active source first, then `*` (Syncthing applies the first matching rule; `*` first syncs nothing) — never sync artifacts, dependency directories, or `.git`. Add a `.oktetoignore` (`.dockerignore` syntax, `[deploy]`/`[test]` sections) when the deploy or test context is large.
- **Persist dependencies and caches** in `dev.<svc>.volumes` and `test.<name>.caches`: Node `node_modules`, Go `/go/pkg/mod` and `/root/.cache/go-build`, Maven `/root/.m2`, Python pip cache and virtualenv.
- **Set `resources.requests` and `resources.limits`** on every dev container — both are unset by default.
- **Get port direction right:** `forward` is `localPort:remotePort`; `reverse` is `remotePort:localPort`.
- **Order Dockerfiles by change frequency** (base and system packages, then dependency install, then source) and never `COPY . .`; use BuildKit cache mounts for dependency and build caches.
- **Validate and rebuild without being asked.** `okteto.yaml`, the Dockerfile, and `.dockerignore` are build inputs — nothing syncs them. Run `okteto validate` as soon as the manifest is written, then `okteto build <service>` and `okteto deploy --wait`, and report the outcome.

## Autonomous mode

When operating without a developer in the loop (e.g. triggered by a ticket or PR), own the full lifecycle. Do not use `okteto up` — it requires a human. Use `okteto deploy` for environments and `okteto test` for validation.

1. Run `okteto context show` to verify the cluster connection
2. Run `okteto deploy --wait` to spin up all services
3. Run `okteto endpoints` to capture live URLs
4. Make the code changes
5. If `okteto.yaml` was modified, run `okteto validate` before proceeding
6. Run `okteto build <service>` and `okteto deploy --wait` to redeploy changed services
7. Run `okteto test <name>` for each test container defined in `okteto.yaml`
8. Check `okteto logs <service> --since 5m` for runtime errors
9. Iterate: fix, rebuild, redeploy, re-test until passing
10. Commit changes, open a PR, and report results (changes made, tests passing, live URL)

Do not run `okteto destroy` unless there is an explicit cleanup policy or instruction.

## CLI reference

| Command | Who runs it | Purpose |
|---------|-------------|---------|
| `okteto deploy --wait` | Agent | Build images and deploy all services |
| `okteto build <service>` | Agent | Rebuild a single service image |
| `okteto up <service>` | **Developer only** | Start interactive dev mode with file sync |
| `okteto exec -- <cmd>` | Agent | Run a command in the active dev container |
| `okteto logs <service>` | Agent | View container logs |
| `okteto endpoints` | Agent | List public URLs for running services |
| `okteto test <name>` | Agent | Run a test container defined in okteto.yaml |
| `okteto down` | Agent or developer | Stop dev mode, restore the deployment |
| `okteto doctor` | Agent | Generate a diagnostic bundle for Okteto support |
| `okteto context show` | Agent | Verify cluster connection and active namespace |
| `okteto validate` | Agent | Validate okteto.yaml syntax before deploying |
| `okteto namespace create <ns>` | Agent | Create an isolated namespace for a worktree |
| `okteto destroy` | Developer; agent only with an explicit cleanup policy | Tear down all resources |

Every command above accepts `-n <ns>` to target a specific namespace without changing the active context — use it to isolate a worktree (see above).

## Mistakes to avoid

- **Running `okteto up` yourself**: It is interactive and will hang. The developer must run it in their terminal.
- **Using `kubectl exec` or direct pod shells**: These bypass Okteto's dev container routing. Use `okteto exec -- <command>` instead.
- **Building Docker images with `docker build`**: Use `okteto build <service>` to use the Okteto Build Service.
- **Mutating the cluster with `kubectl` or `helm`**: `kubectl apply`/`edit`/`delete` and `helm install`/`upgrade` bypass Okteto's resource tracking. Make changes through `okteto deploy`. Read-only kubectl/helm for diagnostics is fine.
- **Hardcoding service names**: Always read `okteto.yaml` to discover them.
- **Running `okteto destroy` without authorization**: It tears down everything. Only run it if the developer explicitly asks or an explicit cleanup policy covers it (see Autonomous mode).
- **Sharing one namespace across worktrees**: Worktrees of the same repo share `okteto.yaml`, so they collide in a shared namespace. Give each its own namespace and pass `-n <ns>` on every command. Don't use `okteto namespace use` for this — it races across concurrent sessions.
