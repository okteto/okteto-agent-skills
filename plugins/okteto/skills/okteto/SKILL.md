---
name: okteto
description: |
  Use when a project contains okteto.yaml or okteto.yml, or when the user
  mentions Okteto, dev environments, or an okteto command. Also use before
  running kubectl, helm, or docker build in a repo that has an Okteto
  manifest; when okteto up hangs or seems stuck; when parallel git worktrees
  collide over the same environment; or when deciding whether okteto destroy
  or okteto namespace delete is safe to run.
license: Apache-2.0
---

# Okteto Development Environment Skill

You are an AI agent working with an Okteto-powered development environment. This skill covers two modes of operation:

1. **Collaborative** -- a developer is actively working with you
2. **Autonomous** -- you are working independently (e.g., triggered by a ticket, PR, or CI pipeline)

## Operating rules

These five rules prevent the most common failures. The rest of this skill elaborates on them.

1. **Read `okteto.yaml` first.** Derive services, builds, and tests from it -- never hardcode names.
2. **Never run `okteto up`.** It is interactive and hangs. The user runs it in collaborative mode; it has no place in autonomous mode.
3. **Mutate the cluster only through Okteto.** Use `okteto build` and `okteto deploy` -- never local `docker build` or `kubectl apply`/`helm upgrade`. Read-only `kubectl`/`helm` (`get`, `describe`, `logs`, `events`, `helm status`) is fine for diagnostics.
4. **One worktree = one namespace.** When working in a git worktree, create a dedicated namespace and pass `-n <ns>` on every command (see [Worktree isolation](#worktree-isolation)).
5. **Never destroy without authorization.** `okteto destroy` and `okteto namespace delete` require explicit policy or instruction (see [Cleanup and teardown](#cleanup-and-teardown)).

## Step 1: Discover the project

Read `okteto.yaml` in the project root. This is the source of truth for:
- **build**: which services have container images
- **deploy**: how services are deployed (usually Helm charts)
- **dev**: which services support development mode, their images, sync paths, and commands
- **test**: which test containers are available and how they run

Parse this file to understand the project's services, languages, and structure. Do not assume hardcoded service names -- always derive them from `okteto.yaml`.

## Step 2: Determine your operating mode

**Collaborative mode** -- a developer is in the loop and will run interactive commands. Use this when:
- A user is chatting with you in an IDE or terminal
- Someone asks you to help debug, set up, or develop a service

**Autonomous mode** -- you are operating independently end-to-end. Use this when:
- Triggered by a ticket (Jira, Linear, GitHub Issue, etc.)
- Running as part of a CI/CD pipeline
- No human is expected to intervene during execution

---

## Collaborative mode

### Environment setup

1. **Check prerequisites**: Run `okteto version` and `okteto context show`
2. **Isolate the worktree** (if applicable): if this is a git worktree, create a namespace per [Worktree isolation](#worktree-isolation) and add `-n <ns>` to every command below
3. **Deploy**: Run `okteto deploy --wait` to build images and deploy all services
4. **Show endpoints**: Run `okteto endpoints` to display the public URLs
5. **Guide the user** to start development on a specific service with `okteto up <service>`

### The `okteto up` rule

**`okteto up` is interactive and MUST be run by the user in their terminal.** It opens a shell inside the development container with live file sync. Never run it yourself -- not as a background task, not with `&`, not at all. Instead, tell the user:

```
Run this in your terminal: okteto up <service>
```

If you are isolating a worktree (see [Worktree isolation](#worktree-isolation)), include the namespace so they attach to the right environment:

```
Run this in your terminal: okteto up <service> -n <ns>
```

### Working with the developer

Once the user has `okteto up <service>` running:

- **Run diagnostics**: `okteto exec -- <command>` to execute commands in the dev container
- **Read synced files**: Use the Read tool to examine code syncing to the cluster
- **Analyze pasted output**: When the user hits an error, they can paste terminal output
- **Check logs**: `okteto logs <service>` for container logs
- **Run tests**: `okteto test <test-name>` for test containers defined in okteto.yaml

You are facilitating their workflow, not trying to observe their terminal session.

### Debugging patterns

| Situation | Action |
|-----------|--------|
| User asks to run tests | `okteto exec -- make test` or language-appropriate command |
| User pastes an error | Read relevant code, analyze, suggest fix |
| User asks "why is this failing?" | Run diagnostics via `okteto exec` |
| User makes source code changes | Changes auto-sync; help them run next steps |
| User changes a build input (Dockerfile, dependencies, `okteto.yaml`) | Nothing syncs -- rebuild and verify (see [When a change needs a rebuild](#when-a-change-needs-a-rebuild-not-a-sync)) |
| User asks to run e2e tests | `okteto test <test-name>` from okteto.yaml |

### When a change needs a rebuild, not a sync

File sync only covers what the running container reads at runtime. It does **not** cover anything baked into the image at build time. After changing any of these, the environment is stale until you rebuild:

- `Dockerfile` or `.dockerignore`
- dependency manifests (`go.mod`/`go.sum`, `package.json`, `requirements.txt`, `pom.xml`, ...)
- compiled binaries, or anything produced by a build step
- `okteto.yaml` itself

Rebuild and confirm it works:

```bash
okteto build <service>      # rebuild the image through the Okteto Build Service
okteto deploy --wait        # redeploy with the new image
```

If `okteto.yaml` changed, run `okteto validate` **before** deploying -- a bad manifest fails mid-deploy and leaves the environment half-updated:

```bash
okteto validate
okteto deploy --wait
```

**Do this without being asked.** A Dockerfile that builds on your machine can still fail in the Build Service -- a file excluded by `.dockerignore`, a missing `go.sum`, a tool version the base image cannot satisfy -- and the only way to find out is to build it. Report the outcome: endpoints on success, the error and your fix on failure. Iterate until it deploys.

**REQUIRED SUB-SKILL:** For a broken or unhealthy environment -- CrashLoopBackOff, OOMKilled, ImagePullBackOff, pods stuck in Pending, deploy failures, or file sync not working -- use the okteto-debugging skill. It has the full triage algorithm and a playbook per failure mode.

---

## Autonomous mode

When operating without a developer in the loop, you own the full lifecycle: environment setup, code changes, validation, and reporting. Do not use `okteto up` -- it is interactive and requires a human. Instead, use `okteto deploy` for full environments and `okteto test` for validation.

### Workflow

1. **Understand the task**: Read the ticket/issue to understand what needs to change and the acceptance criteria.

2. **Deploy an environment**:
   - Run `okteto context show` to verify cluster connection and see the active namespace
   - If this run is one of several parallel branches/worktrees, create an isolated namespace first (see [Worktree isolation](#worktree-isolation)) and pass `-n <ns>` on every command below
   - Run `okteto deploy --wait` to spin up all services
   - Run `okteto endpoints` to capture the live URLs for later validation

3. **Make code changes**: Edit the relevant source files based on the task requirements. Use the Read tool, Grep, and Glob to explore the codebase. Inspect the service directories and `okteto.yaml` to understand service structure.

4. **Rebuild and redeploy changed services**:
   - If `okteto.yaml` was modified, run `okteto validate` **before** deploying -- a bad manifest fails mid-deploy and leaves the environment half-updated
   - Run `okteto build <service>` to rebuild only the changed service image
   - Run `okteto deploy --wait` to redeploy with the updated image
   - Alternatively, if only one service changed, target it: `okteto build <service> && okteto deploy --wait`
   - Do this after **any** change to a build input -- Dockerfile, `.dockerignore`, dependency manifest, `okteto.yaml` -- not just source code. Nothing syncs in autonomous mode; the environment is stale until you redeploy.

5. **Validate**:
   - Run `okteto test <test-name>` for each test container in okteto.yaml
   - Run `okteto endpoints` and use curl or similar to smoke-test the live endpoints
   - Check `okteto logs <service> --since 5m` for errors in the changed services

6. **Iterate if tests fail**:
   - Read test output and logs to diagnose the failure
   - Fix the code, rebuild, redeploy, and re-test
   - Repeat until all tests pass

7. **Report results**: Summarize what was changed, what tests passed, and provide the live environment URL for review. Include any relevant log output or test artifacts.

8. **Clean up**: Follow the rules in the [Cleanup and teardown](#cleanup-and-teardown) section below. Do not destroy without explicit authorization or a predefined cleanup policy.

### Autonomous example

```
Trigger: Jira ticket "PROJ-123: Add rate limiting to /api/rentals endpoint"

Agent actions (worktree on branch proj-123, isolated namespace ns=proj-123):
  1. Read ticket for requirements and acceptance criteria
  2. okteto namespace create proj-123  -> isolated namespace for this worktree
  3. okteto deploy --wait -n proj-123  -> full environment running
  4. Read okteto.yaml, explore api/ directory
  5. Edit api/handlers/rentals.go      -> implement rate limiting
  6. Edit api/handlers/rentals_test.go  -> add unit tests
  7. okteto build api -n proj-123      -> rebuild the api service image
  8. okteto deploy --wait -n proj-123  -> redeploy with changes
  9. okteto test e2e -n proj-123       -> run e2e test suite
  10. okteto logs api --since 5m -n proj-123  -> check for runtime errors
  11. curl the live endpoint to verify rate limiting behavior
  12. Commit changes, open PR
  13. Report back to PROJ-123: changes made, tests passing, PR link, live URL
```

(On a single non-worktree checkout, drop the `okteto namespace create` step and the `-n` flags -- the context's default namespace is fine.)

---

## Worktree isolation

An Okteto **namespace** is the unit of isolation -- it holds everything `okteto deploy` creates. The namespace comes from your active Okteto context (`~/.okteto`), which is **global to the machine**, not per-directory. That matters the moment you work in more than one checkout at once.

A single primary checkout (not a worktree) can use its context's default namespace -- no `-n` needed, and you can skip this section. Only reach for a dedicated namespace when parallel checkouts or worktrees would otherwise collide. The rest of this skill omits `-n` for brevity; **add it to every command when you are isolating a worktree.**

### One worktree = one namespace

If you are working in a **git worktree** (or any second checkout of the same repo), you share the *same `okteto.yaml`* as the other worktrees -- same Helm releases, same resource names. If two worktrees deploy into the same namespace:
- the second `okteto deploy` **overwrites** the first's environment,
- `okteto endpoints` / `okteto logs` return the wrong worktree's data,
- an `okteto destroy` in one worktree **tears down the other's environment**.

Give each worktree its own namespace so the separation is complete.

**Detect a worktree** (when in doubt, check):

```bash
git rev-parse --git-common-dir   # differs from `git rev-parse --git-dir` -> you are in a linked worktree
git worktree list                # shows all worktrees of this repo
git branch --show-current        # the branch is a good basis for the namespace name
```

**Derive the namespace name** from the branch (or worktree directory). Okteto namespace names must be lowercase alphanumeric and `-`, start and end with an alphanumeric character, and be at most 63 characters (regex `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$`):

```bash
# branch "feat/Rate_Limiting" -> "feat-rate-limiting"
ns=$(git branch --show-current | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/^-*//; s/-*$//' | cut -c1-50)
```

If your team has a naming convention (e.g. `agent-<branch>` or `<user>-<branch>`), follow it.

### Create once, then pass `-n` on every command

```bash
okteto namespace create <ns>     # creates it; reports if it already exists
```

Then **pass `-n <ns>` on every Okteto command for the rest of the session**:

```bash
okteto deploy --wait -n <ns>
okteto build <service> -n <ns>
okteto endpoints -n <ns>
okteto logs <service> -n <ns>
okteto test <name> -n <ns>
okteto destroy -n <ns>
```

**Do not use `okteto namespace use <ns>` to isolate worktrees.** It switches the *active* namespace in the shared global context, which races with any other worktree or agent on the same machine -- silently redirecting their commands too. The `-n` flag is per-invocation and never mutates shared state, so it is safe under concurrency. (`okteto namespace use` is fine only when you have a single checkout and nothing else is running against the same context.)

---

## Cleanup and teardown

Tearing down an environment is as important as standing one up. Get the command right, and get the authorization right.

### Pick the right command

| Command | What it does | When to use |
|---------|--------------|-------------|
| `okteto down` | Exits dev mode for one service; restores the original deployment. **Does not destroy the environment.** | The developer is done iterating on a service but wants the environment to keep running. |
| `okteto destroy` | Tears down every resource created by `okteto deploy` in the current namespace. **Destructive.** | The environment is no longer needed and teardown is authorized. |
| `okteto namespace delete <name>` | Deletes an entire namespace and everything in it. **Very destructive.** | Only for a namespace the agent itself created for an isolated worktree (see [Worktree isolation](#worktree-isolation)), or with explicit user instruction. **Never** for a shared or pre-existing namespace as cleanup from a task. |

A common mistake is reaching for `okteto destroy` when the user only wanted to exit dev mode. If in doubt, `okteto down` is the safe choice.

### Tearing down an isolated worktree namespace

If you created a dedicated namespace for a worktree (see [Worktree isolation](#worktree-isolation)), that namespace is yours to remove once the work is done and the worktree is going away:

```bash
okteto destroy -n <ns>           # remove the deployed resources
okteto namespace delete <ns>     # then remove the now-empty namespace you created
```

This is the one case where `okteto namespace delete` is appropriate without a separate instruction -- you created it, so you own its teardown. It does **not** override the rule below for namespaces you did *not* create.

### Collaborative mode

Do not run `okteto destroy` yourself. Surface it as a suggestion and let the developer run it:

```
You're done with this environment. To tear it down, run:
  okteto destroy
```

`okteto down` is fine for the agent to run when the developer has clearly finished with a service.

### Autonomous mode

Run `okteto destroy` only when one of these is true:

- The task explicitly authorizes cleanup (e.g., "destroy the environment when the PR is merged")
- There is a predefined cleanup policy documented in the repo's `CLAUDE.md` or the ticket
- The environment is ephemeral and owned by the pipeline (e.g., a per-run preview environment)

If none of those apply, leave the environment running and note in the report that it is still up, with the command the caller would use to tear it down. It is always safer to leave a running environment than to destroy one that someone else depended on.

### Never do this

- Delete a namespace you did not create
- Destroy a shared or named environment (e.g., `staging`, `dev`) without explicit instruction
- Treat `okteto destroy` as a recovery step when something goes wrong — diagnose first

---

## Discovering dev commands

Look at the `dev` section of `okteto.yaml` for each service. The `command` field tells you how the service starts:

- If `command: bash` -- the service needs manual build/start (check for Makefile, package.json, pom.xml in the service directory)
- If `command: yarn start` or `command: mvn spring-boot:run` -- the service auto-starts in dev mode
- Check for `Makefile`, `package.json`, `pom.xml`, or `go.mod` in the service directory to determine available commands

## CLI quick reference

| Command | Collaborative | Autonomous | Purpose |
|---------|:---:|:---:|---------|
| `okteto deploy --wait` | Agent | Agent | Build images and deploy all services |
| `okteto build <service>` | Agent | Agent | Build and push a single service image |
| `okteto up <service>` | **User only** | **Never** | Start interactive dev container |
| `okteto down` | Agent/User | N/A | Stop dev mode, restore deployment |
| `okteto exec -- <cmd>` | Agent | N/A | Run command in active dev container |
| `okteto logs <service>` | Agent | Agent | View container logs |
| `okteto endpoints` | Agent | Agent | List public URLs |
| `okteto test <name>` | Agent | Agent | Run a test container from okteto.yaml |
| `okteto destroy` | User | With policy | Tear down all resources |
| `okteto doctor` | Agent | Agent | Generate a diagnostic bundle |
| `okteto status` | Agent | N/A | Check file sync progress |
| `okteto validate` | Agent | Agent | Validate okteto.yaml manifest syntax |
| `okteto context show` | Agent | Agent | Verify cluster and namespace |
| `okteto namespace create <ns>` | Agent | Agent | Create an isolated namespace for a worktree |
| `okteto namespace list` | Agent | Agent | List namespaces you have access to |
| `okteto namespace delete <ns>` | User | Self-created only | Delete a namespace (only one you created) |

**`-n <ns>` flag:** every command above (`deploy`, `build`, `up`, `down`, `exec`, `logs`, `test`, `endpoints`, `destroy`) accepts `-n <ns>` to target a specific namespace without changing the active context. Use it -- not `okteto namespace use` -- to isolate a worktree (see [Worktree isolation](#worktree-isolation)).

## Common mistakes to avoid

- **Running `okteto up` in autonomous mode**: There is no human to interact with the shell. Use `okteto deploy` + `okteto build` + `okteto test` instead.
- **Running `okteto up` as the agent in collaborative mode**: It is interactive. Always tell the user to run it.
- **Forgetting to deploy first**: Run `okteto deploy` before any validation or testing.
- **Not specifying the service**: With multiple services, always specify which one.
- **Using kubectl/helm to change the cluster**: Mutations (`kubectl apply`, `kubectl delete`, `helm upgrade`, ...) must go through `okteto deploy` so Okteto can track resources. Read-only kubectl/helm for diagnostics is fine.
- **Building Docker images locally**: Use `okteto build` to leverage the Okteto Build Service.
- **Hardcoding service names**: Always read `okteto.yaml` to discover services.
- **Destroying without authorization**: In autonomous mode, do not run `okteto destroy` unless there is an explicit cleanup policy or instruction.
- **Sharing one namespace across worktrees**: Two worktrees deploying into the same namespace overwrite each other and a `destroy` in one wipes the other. Give each worktree its own namespace (see [Worktree isolation](#worktree-isolation)) and pass `-n <ns>` on every command.
- **Using `okteto namespace use` to isolate concurrent work**: It mutates the global active context and races with other worktrees/agents. Use the per-command `-n <ns>` flag instead.
