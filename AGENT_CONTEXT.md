# Okteto Agentic Workflows - Context for Docs Agent

## Background

Okteto customers are increasingly using AI agents (Claude Code, etc.) as first-class developers in their environments. We built a Claude Code plugin to make this easy without requiring per-repo configuration files. This document captures the context needed to update Okteto docs for agentic workflow support.

## Customer Insights

From conversations with prospects evaluating Okteto for agentic workflows, their desired end state includes:

- **Agents as first-class citizens**: AI agents spin up their own isolated Okteto environments, just like human developers do
- **One unified remote environment**: The same environment works for both humans and agents -- no separate infra
- **Environments defined as code**: All config lives in version control (`okteto.yaml`), reviewable and reproducible
- **Standardized base images**: Curated, versioned base images ensure deterministic behavior regardless of who or what launched the environment
- **Stateful services are resettable**: Databases and message queues start from a shared baseline, revertable to clean state
- **Shared service overlay**: Environments can connect to already-running services in a testing environment instead of standing up every dependency
- **PR preview environments**: Every PR gets a running environment that stakeholders can access without local setup
- **No environment drift**: What works in one environment works in all of them
- **Security and cost controls**: Isolation, access controls, auto-shutdown on idle
- **Remote authoring**: Developers connect to remote dev environments from their IDE via standard protocols

## Two Operating Modes

The plugin teaches agents two distinct workflows:

### 1. Collaborative Mode (Human-in-the-Loop)

A developer is actively working with the agent in an IDE or terminal.

- Agent runs `okteto deploy --wait` to set up the environment
- Developer runs `okteto up <service>` in their terminal (interactive -- agent must never run this)
- Agent uses `okteto exec -- <command>` to run diagnostics, tests, builds in the dev container
- Agent uses `okteto logs <service>` to check container output
- Agent uses `okteto test <test-name>` to run test containers
- Code changes auto-sync to the dev container via file sync

Key rule: `okteto up` is interactive and must always be run by the human, never the agent.

### 2. Autonomous Mode (No Human in the Loop)

Agent operates end-to-end, triggered by a ticket, PR, or CI pipeline.

Workflow:
1. Read ticket/issue for requirements and acceptance criteria
2. `okteto deploy --wait` to spin up full environment
3. `okteto endpoints` to capture live URLs
4. Make code changes based on requirements
5. `okteto build <service>` to rebuild changed service images
6. `okteto deploy --wait` to redeploy
7. `okteto test <test-name>` to validate
8. Smoke-test live endpoints with curl
9. `okteto logs <service> --since 5m` to check for errors
10. Iterate on failures (fix, rebuild, redeploy, re-test)
11. Commit, open PR, report results back to ticket

Key rule: Never use `okteto up` in autonomous mode. Use `okteto deploy` + `okteto build` + `okteto test` instead.

## Auto-Discovery via okteto.yaml

A core design principle: agents should not need hardcoded service lists or per-repo config files. Instead, the agent reads `okteto.yaml` to discover:

- **`build` section**: Which services have container images
- **`deploy` section**: How services are deployed (usually Helm charts)
- **`dev` section**: Which services support dev mode, their images, sync paths, startup commands
- **`test` section**: Which test containers are available and their commands

This makes the plugin work across any Okteto project without maintenance.

## Worktree Isolation via Namespaces

A key requirement for agentic workflows: when an agent works across multiple **git worktrees** (parallel branches/features), each worktree must use its **own Okteto namespace** for complete separation of concerns. This is the concrete realization of the "agents as first-class citizens / isolated environments" insight above.

Why it matters: worktrees of the same repo share the same `okteto.yaml`, so they produce the same Helm release and resource names. The Okteto namespace comes from the active context (`~/.okteto`), which is global to the machine. Without isolation, two worktrees deploy into the same namespace and collide — the second `okteto deploy` overwrites the first, logs/endpoints cross over, and `okteto destroy` in one tears down the other.

The plugin teaches:
- **One worktree = one namespace.** Derive the name from the branch (lowercase alphanumeric and `-`, ≤ 63 chars), create it with `okteto namespace create <ns>`.
- **Pass `-n <ns>` on every command** rather than `okteto namespace use` — the flag is per-invocation and safe when multiple worktree agents run concurrently; `namespace use` mutates the shared global context and races.
- **Self-created namespaces are the agent's to delete** at cleanup (`okteto destroy -n <ns>` then `okteto namespace delete <ns>`), unlike shared namespaces.

## CLI Commands for Docs Reference

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
| `okteto namespace create <ns>` | Agent | Agent | Create an isolated namespace for a worktree |
| `okteto destroy` | User | With policy | Tear down all resources |

Every command accepts `-n <ns>` to target a namespace without changing the active context — this is the mechanism for worktree isolation (see below).

## Plugin Distribution

The plugin is published at: https://github.com/okteto/okteto-agent-skills

Users install with:
```
/plugin marketplace add okteto/okteto-agent-skills
/plugin install okteto
```

Contents:
- `.claude-plugin/marketplace.json` -- Marketplace manifest (repo root)
- `plugins/okteto/.claude-plugin/plugin.json` -- Plugin metadata
- `plugins/okteto/skills/okteto/SKILL.md` -- Main skill covering both operating modes
- `plugins/okteto/skills/onboarding/SKILL.md` -- Onboarding skill for repos with no `okteto.yaml` yet
- `plugins/okteto/skills/okteto-debugging/SKILL.md` -- Environment triage skill with a playbook per pod failure mode
- `plugins/okteto/commands/dev-setup.md` -- `/dev-setup` slash command for environment setup
- `plugins/okteto/commands/debug-env.md` -- `/debug-env` slash command for a read-only environment health sweep
- `plugins/okteto/hooks/` -- Guardrail hooks (destructive-command guard, session-start context)
- `tests/` -- Eval harness for the plugin (`run-evals.sh`, fixtures, mock model)
- `examples/` -- Reference CI pipelines (e.g. `ticket-to-pr.yml` autonomous pipeline)
- `agents/AGENTS.md`, `copilot/copilot-instructions.md` -- Same guidance packaged for other agent harnesses

## What the Docs Should Cover

Suggested documentation areas based on customer conversations:

1. **Getting started with AI agents on Okteto** -- How to install the plugin and run your first agent-assisted dev session
2. **Collaborative workflows** -- How agents and developers work together with `okteto up` + `okteto exec`
3. **Autonomous workflows** -- How to set up ticket-to-PR pipelines where agents own the full lifecycle
4. **okteto.yaml as the single source of truth** -- How agents auto-discover services, no extra config needed
5. **The `okteto up` rule** -- Why agents must never run `okteto up` and what to use instead
6. **Testing with agents** -- How `okteto test` enables agents to validate changes against live environments
7. **Preview environments for agents** -- How each agent gets isolated environments that don't conflict
8. **Worktree isolation with namespaces** -- How agents working across multiple git worktrees use a namespace per worktree (`okteto namespace create` + `-n <ns>`) so parallel work never collides

## Common Pitfalls to Document

- Agent tries to run `okteto up` (it hangs -- it's interactive)
- Agent mutates the cluster with kubectl/helm (`apply`, `edit`, `delete`, `helm upgrade`) instead of `okteto deploy` (Okteto loses track of resources) — read-only kubectl/helm for diagnostics is fine
- Agent builds Docker images locally instead of using `okteto build` (no access to Okteto Build Service)
- Agent hardcodes service names instead of reading `okteto.yaml` (breaks portability)
- Agent runs `okteto destroy` without authorization (destroys shared resources)
- Agent runs multiple worktrees in one shared namespace (they overwrite each other; a `destroy` in one wipes the others) — use a namespace per worktree with `-n <ns>`
- Agent uses `okteto namespace use` to switch namespaces for concurrent worktrees (races on the shared global context) — use the per-command `-n <ns>` flag instead
