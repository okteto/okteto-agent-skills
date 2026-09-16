# Okteto Plugins for AI Agents

Teaches AI agents how to work with [Okteto](https://www.okteto.com) development environments. Works with any project that has an `okteto.yaml`.

Built on the open [Agent Skills](https://agentskills.io) format, so the same skills run in **Claude Code**, **Cursor**, **OpenAI Codex**, **GitHub Copilot**, **Antigravity CLI (formerly Gemini CLI)**, and [many more](https://agentskills.io/clients).

## Install

Pick the row for your agent. Every method teaches the agent the same Okteto workflows — they differ only in packaging.

| Your agent | Install | You get |
|---|---|---|
| **Claude Code** | `/plugin marketplace add okteto/okteto-agent-skills` → `/plugin install okteto` | All five skills **+ the `/dev-setup` and `/debug-env` commands** |
| **Cursor, Codex, Copilot, Antigravity CLI (formerly Gemini CLI), [& more](https://agentskills.io/clients)** | `npx skills add okteto/okteto-agent-skills` | All five skills, installed into your agent |
| **Anything that reads `AGENTS.md`** | `cp agents/AGENTS.md <your-repo>/AGENTS.md` | One always-on instruction file |
| **GitHub Copilot (file-based)** | `cp copilot/copilot-instructions.md <your-repo>/.github/copilot-instructions.md` | One always-on instruction file |

Requires the [Okteto CLI](https://www.okteto.com/docs/get-started/install-okteto-cli/) installed and configured, and an `okteto.yaml` in your project.

### Claude Code (native plugin)

Run these two commands inside Claude Code:

```
/plugin marketplace add okteto/okteto-agent-skills
/plugin install okteto
```

- `/plugin marketplace add okteto/okteto-agent-skills` — tells Claude Code to trust this GitHub repo as a source of plugins. One-time registration.
- `/plugin install okteto` — installs the `okteto` plugin, wiring up its skills **and** the `/dev-setup` and `/debug-env` slash commands.

After install, open any project with an `okteto.yaml` and ask Claude for help. The skills activate automatically; `/dev-setup` is available whenever you want a guided environment bring-up, and `/debug-env` runs a read-only health sweep of the environment. This is the only method that includes the slash commands and the guardrail hooks below.

#### Guardrail hooks (Claude Code only)

The plugin ships hooks that enforce the skill's two hardest rules mechanically, so a session can't wedge even if the model forgets them:

- **`okteto up` is always denied** with a message telling the agent to hand the command to you — it's interactive and would hang the agent's shell.
- **`okteto destroy`, `okteto preview destroy`, and `okteto namespace delete` require confirmation.** You approve them per-invocation. Pipelines that own their environments (e.g. per-PR preview environments) can pre-authorize teardown by setting `OKTETO_ALLOW_AGENT_DESTROY=1` — this is the mechanical form of the skill's "explicit cleanup policy" rule.
- **Sessions in Okteto projects start informed.** A `SessionStart` hook detects `okteto.yaml` at the repo root and injects a reminder that this is an Okteto project and that changes should be verified in an Okteto environment — making skill activation deterministic instead of description-matching luck, even when the prompt never mentions Okteto (e.g. "implement this feature").

The hooks fail open: if their input can't be parsed they allow the command, so they can only ever tighten `okteto` invocations, never break your session. They require a POSIX shell (macOS/Linux/WSL).

### Cursor, Codex, and other skills-compatible agents (`npx skills`)

The [`skills`](https://github.com/vercel-labs/skills) CLI installs the skills into whichever agent you run it from — no Okteto-specific config required:

```
npx skills add okteto/okteto-agent-skills
```

It auto-detects your agent (Cursor, Codex, Copilot, Antigravity CLI (formerly Gemini CLI), and [others](https://agentskills.io/clients)) and prompts you to pick skills. Useful flags:

- `--skill '*' -y` — install all skills into the detected agent without prompting
- `--copy` — copy the skill files in instead of symlinking them
- `npx skills use okteto/okteto-agent-skills@okteto` — print a skill as a one-off prompt without installing it

Avoid `--all` — it installs into *every* known agent's directory, not just yours.

This carries the **skills only** — the `/dev-setup` and `/debug-env` slash commands are exclusive to the Claude Code plugin above.

### File-based fallback (`AGENTS.md` / Copilot)

If your agent reads a plain instruction file, copy one in — zero dependency on any installer:

```
cp agents/AGENTS.md <your-repo>/AGENTS.md                                  # AGENTS.md-aware agents
cp copilot/copilot-instructions.md <your-repo>/.github/copilot-instructions.md   # GitHub Copilot
```

Both files carry the same tool-neutral Okteto guidance: discovering services from `okteto.yaml`, using `okteto exec` (not `kubectl exec`), treating `okteto up` as developer-only, when to `okteto build` vs. rely on sync, and isolating worktrees with `-n <ns>`. **Cursor** users can alternatively drop the same content at `.cursor/rules/okteto.mdc` for native rule scoping. Unlike the skills methods, these load the full instructions on every turn rather than on demand.

## What's included

- **`okteto` skill** -- CLI knowledge, collaborative and autonomous workflow patterns, worktree isolation, cleanup rules
- **`okteto-onboarding` skill** -- Bootstraps projects that have no `okteto.yaml` yet: discovers services, drafts a manifest, validates it, then hands off to the `okteto` skill
- **`okteto-debugging` skill** -- Triages broken environments: a triage algorithm plus a playbook per failure mode (CrashLoopBackOff, OOMKilled, ImagePullBackOff, Pending, runtime errors, deploy failures, sync issues)
- **`okteto-preview` skill** -- Preview environments for branches and pull requests: deploying with `okteto preview deploy`, capturing endpoints and posting the URL back to the PR or thread, mapping the flow to CI (`okteto/deploy-preview` GitHub Action, GitLab CI/CD), and teardown rules
- **`okteto-manifest-optimizer` skill** -- Reviews and rewrites an existing `okteto.yaml` for performance: pins images, scopes the build/sync context with `.dockerignore`/`.oktetoignore`/`.stignore` (in the order each tool reads them), persists dependencies in `dev.<svc>.volumes` and `test.<name>.caches`, sets `resources`, gets `forward`/`reverse` right, runs a ten-item review checklist against Okteto's optimization best practices, then validates and rebuilds
- **`/dev-setup` command** (Claude Code only) -- One-command environment setup: checks prerequisites, deploys services, shows endpoints, guides the developer into a dev container
- **`/debug-env` command** (Claude Code only) -- Read-only health sweep: triages every unhealthy service (or one, with `/debug-env <service>`) and emits a structured root cause + fix per service
- **Guardrail hooks** (Claude Code only) -- Deterministically block `okteto up` (it would hang the agent), require confirmation for `okteto destroy`/`okteto preview destroy`/`okteto namespace delete`, and announce Okteto projects at session start

## Usage

### Skill (automatic)

The Okteto skill activates automatically when a project has an `okteto.yaml`. It teaches the agent:

- How to discover services from `okteto.yaml` (no hardcoded config needed)
- When to use `okteto deploy`, `okteto build`, `okteto test`, `okteto exec`, and `okteto logs`
- That `okteto up` is interactive and must be run by the developer, never the agent
- How to operate in **collaborative mode** (developer in the loop) vs **autonomous mode** (ticket-driven, no human)
- How to isolate **git worktrees**: one namespace per worktree (`okteto namespace create` + `-n <ns>` on every command) so parallel branches never overwrite each other's environments
- How to tear environments down cleanly with `okteto destroy` and when it is (and isn't) safe for an agent to do so unprompted

### `okteto-onboarding` skill (automatic)

The `okteto-onboarding` skill activates when a repo has no `okteto.yaml` and the user wants to get the project onto Okteto. It:

- Discovers services from `docker-compose.yml`, Helm charts, Kubernetes manifests, or Dockerfiles
- Drafts an `okteto.yaml` based on what it finds
- Validates the manifest through a tiered ladder: `okteto validate` → `okteto build` → `okteto deploy --wait`
- Hands off to the `okteto` skill once the manifest exists

Once the `okteto.yaml` is in place, normal `okteto` skill workflows (collaborative mode, autonomous mode, `/dev-setup`) take over.

### `okteto-debugging` skill (automatic)

The `okteto-debugging` skill activates when a service or environment is unhealthy — "my service keeps crashing", "pods are stuck in Pending", or pasted output showing `CrashLoopBackOff`. It:

- Snapshots pod states with `kubectl get pods` and applies a playbook per failure mode (crash loops, OOM kills, image pull failures, unschedulable pods, runtime errors, deploy failures, sync issues)
- Gathers evidence with read-only kubectl (`describe`, `logs --previous`, `get events`) — it never mutates the cluster
- Emits a structured diagnosis per unhealthy service: root cause, evidence, exact fix, and a confidence rating

In Claude Code, `/debug-env` (optionally scoped to one service: `/debug-env catalog`) runs the same triage as a deliberate full sweep.

### `okteto-preview` skill (automatic)

The `okteto-preview` skill activates when someone wants a live, shareable environment for a branch or pull request. It teaches the agent:

- When a task needs a **preview environment** (a shareable URL for reviewers, deployed from a pushed branch) vs. a **namespace dev environment** (the agent's own workbench, deployed from the working tree)
- How to deploy a preview for a branch or PR with `okteto preview deploy`, including scope (`personal` vs `global`), variables, and naming conventions that keep redeploys and cleanup idempotent
- How to capture endpoints (`okteto preview endpoints -o md`) and post the preview URL back to the PR (`gh pr comment`) or thread
- How the same flow runs in CI with the `okteto/deploy-preview` and `okteto/destroy-preview` GitHub Actions (or GitLab CI/CD jobs)
- Teardown rules matching the `okteto` skill's cleanup doctrine: previews the agent created are its to destroy; CI-owned and shared/global previews are not

### `okteto-manifest-optimizer` skill (automatic)

The `okteto-manifest-optimizer` skill activates when a repo already has an `okteto.yaml` and someone wants it faster or reviewed — "make my dev environment start faster", "review this manifest for performance", "why is the initial sync so slow". It:

- Encodes Okteto's [manifest performance best practices](https://www.okteto.com/docs/tutorials/optimize-your-development-environment/): pinned images, layer-ordered Dockerfiles with BuildKit cache mounts, `.dockerignore`/`.oktetoignore`/`.stignore` scoping, precopied dev images, and Volume Snapshots over slow seed scripts
- Wires dev images with `${OKTETO_BUILD_<NAME>_IMAGE}`, persists dependencies in `dev.<svc>.volumes` and `test.<name>.caches`, sets `resources.requests`/`limits`, and gets `forward` (`local:remote`) vs `reverse` (`remote:local`) direction right
- Runs a ten-item review checklist, then `okteto validate`, then rebuilds and redeploys the way the `okteto` skill requires — a changed manifest is a build input and does not sync

Day-to-day development stays with the `okteto` skill, and first-time service discovery on a repo with no manifest stays with `okteto-onboarding` (optimize its draft here once it deploys).

### Cleanup and teardown

The skill covers the end of the lifecycle as well as the start. It teaches the agent:

- To run `okteto destroy` to tear down all resources created by `okteto deploy`
- To use `okteto down` (not `okteto destroy`) to exit dev mode without destroying the environment
- To treat `okteto destroy` as a destructive action: in **collaborative mode** it asks the developer to run it; in **autonomous mode** it only runs when there is an explicit cleanup policy or authorization (e.g., an ephemeral PR environment that the pipeline owns)
- To leave shared namespaces alone unless the task explicitly scopes cleanup to a namespace the agent owns
- That a namespace it created itself for an isolated worktree *is* the agent's to delete (`okteto destroy -n <ns>` then `okteto namespace delete <ns>`)

If your team wants different defaults (for example, always destroy on autonomous run success), document that in your repo's `CLAUDE.md` and the skill will pick it up.

### `/dev-setup` command (Claude Code only)

Run `/dev-setup` to have the agent walk through full environment setup:

1. Reads `okteto.yaml` to discover services
2. Checks CLI prerequisites (`okteto version`, `okteto context show`)
3. Deploys all services (`okteto deploy --wait`)
4. Shows live endpoints (`okteto endpoints`)
5. Guides you to start developing a specific service

### Autonomous mode

For CI/CD or ticket-driven workflows where no developer is present, the skill teaches agents to:

1. Deploy a full environment with `okteto deploy --wait`
2. Make code changes based on ticket requirements
3. Rebuild and redeploy changed services with `okteto build` + `okteto deploy`
4. Validate with `okteto test` and endpoint smoke tests
5. Report results back to the ticket/PR

A complete, copy-pasteable GitHub Actions implementation of this flow — issue labeled `agent` → isolated namespace → implement → test → PR with the preview URL → teardown on PR close — lives at [examples/ticket-to-pr.yml](examples/ticket-to-pr.yml), with a full walkthrough (required secrets, teardown policy, security notes) in [examples/README.md](examples/README.md).

## Testing the plugin

For interactive poking, load the plugin into a session:

```
claude --plugin-dir /path/to/okteto-agent-skills/plugins/okteto
```

For repeatable checks there is a scripted eval harness. It runs headless
Claude Code sessions against the repos in `tests/fixtures/` with the plugin
loaded, and asserts on the stream-json transcript (tool calls, hook denials)
and on a fake `okteto` CLI (`tests/bin/okteto`) that logs every invocation and
returns canned output — no live cluster needed.

```
tests/run-evals.sh                 # everything (agent layer skips without auth)
tests/run-evals.sh --layer hooks   # hook-script unit tests: bash + jq only
tests/run-evals.sh --layer wiring  # in-harness guard checks: no API key needed
tests/run-evals.sh --layer agent   # live model evals: needs claude auth
```

The three layers, cheapest first:

| Layer | What it proves | Needs |
|---|---|---|
| `hooks` | `guard-okteto.sh` denies `okteto up`, escalates `okteto destroy`/`namespace delete` to *ask*, honors `OKTETO_ALLOW_AGENT_DESTROY=1`, fails open on bad input; `session-start.sh` announces the manifest | bash, jq |
| `wiring` | The same guarantees hold *inside a real headless session*: a mock Messages API (`tests/mock-model/server.py`) force-feeds scripted tool calls, so the PreToolUse deny, the headless ask→block behavior, and the shim round-trip are verified deterministically | + claude, python3 |
| `agent` | A live model given realistic prompts follows the skills: never executes `okteto up`, refuses to onboard over an existing `okteto.yaml`, isolates git worktrees with `okteto namespace create` + `-n` flags, never destroys without authorization, and, from a realistic "my environment is slow" complaint, loads `okteto-manifest-optimizer` and rewrites an `okteto.yaml` per repo archetype that is then gated by the real `okteto validate`, a deterministic rubric, and an LLM judge (no `:latest`, `${OKTETO_BUILD_*_IMAGE}` wiring, `.dockerignore`/`.stignore` scoped in the right order, persisted deps, `resources`, correct `forward`/`reverse`, `test.caches`) | + claude auth |

For the agent layer, set `ANTHROPIC_API_KEY` or be logged in (`claude login`);
the harness probes auth first and skips with a notice if neither works.
`CLAUDE_EVAL_MODEL` overrides the model (default `claude-sonnet-5`), and
`--scenario <name>` runs a single agent scenario. Transcripts, shim logs, and
mock-server logs land in a temp dir printed at the end of every run.

The agent layer judges *behavior*: a scenario can legitimately be stopped at
the skill layer (the model never tries the forbidden command) or at the hook
layer (the guard denies it). Both count as the guardrail holding; the output
notes which layer fired. Live-model runs are inherently somewhat
nondeterministic — if a behavioral scenario fails, read the transcript in the
artifacts dir before blaming the plugin.

In CI, `.github/workflows/evals.yml` runs the `hooks` and `wiring` layers on
every pull request (they need no secrets) and the `agent` layer only when the
`ANTHROPIC_API_KEY` repository secret is configured, skipping it gracefully
otherwise.

## Requirements

- [Okteto CLI](https://www.okteto.com/docs/get-started/install-okteto-cli/) installed and configured
- An `okteto.yaml` in your project root (use the `okteto-onboarding` skill if you don't have one yet)
- A skills-compatible agent — see the [Install](#install) table

---

_Open-source (Apache-2.0), separate from the Okteto product, not covered by support SLAs._
