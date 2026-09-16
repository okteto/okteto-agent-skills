# Examples

Working reference pipelines for the okteto plugin. Everything here is meant to be copied into your own application repo and adapted — and everything here needs a real [Okteto](https://www.okteto.com) instance to actually run.

## `ticket-to-pr.yml` — autonomous ticket-to-PR pipeline

The okteto skill describes an [autonomous mode](../plugins/okteto/skills/okteto/SKILL.md) for ticket-driven work with no human in the loop. This workflow is that mode made concrete: a GitHub Actions pipeline that runs [Claude Code](https://code.claude.com) headless via [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action) with this plugin loaded, and follows the skill's own doctrine step by step.

### What a run looks like

1. Someone adds the **`agent` label** to a GitHub issue in your application repo.
2. The workflow checks out your app and this plugin repo, installs the Okteto CLI, and connects to your Okteto instance.
3. Claude Code starts in autonomous mode with the okteto plugin loaded and the issue as its task. It then follows the skill's autonomous workflow:
   - creates a branch (`agent/issue-42`) and an **isolated namespace derived from it** (`agent-issue-42`),
   - `okteto deploy --wait -n agent-issue-42` to bring up the full environment,
   - reads `okteto.yaml` to discover services, implements the change,
   - `okteto build <service>` + `okteto deploy --wait` to redeploy what changed,
   - `okteto test` for each test container, plus `curl` smoke tests against the live `okteto endpoints`,
   - opens a **PR with the preview URL** in the body, and comments the summary + links back on the issue.
4. The preview environment **stays running for reviewers**. When the PR closes (merged or not), the `cleanup` job destroys the namespace. If the run fails partway, a failure step tears it down immediately and comments on the issue.

### Setup

1. Copy `ticket-to-pr.yml` into your application repo as `.github/workflows/ticket-to-pr.yml`. Your repo needs an `okteto.yaml` (use the plugin's `okteto-onboarding` skill if it doesn't have one yet) — ideally with `test:` containers, since that's what the agent runs to validate its work.
2. Create the `agent` label in the repo (Issues → Labels).
3. Configure credentials in the repo (Settings → Secrets and variables → Actions):

   | Name | Kind | What it is |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | Secret | Anthropic API key that Claude Code runs on. |
   | `OKTETO_TOKEN` | Secret | An Okteto [personal access token](https://www.okteto.com/docs/core/credentials/personal-access-tokens/) for the account the pipeline deploys as. |
   | `OKTETO_URL` | Variable | The URL of your Okteto instance, e.g. `https://okteto.example.com`. |

4. Allow the workflow to open PRs: Settings → Actions → General → **"Allow GitHub Actions to create and approve pull requests"**. Without this, `gh pr create` with the workflow's own token is rejected.
5. Label an issue `agent` and watch the run.

### How the plugin is loaded

CI can't run the interactive `/plugin install` flow, so the workflow checks this repo out next to your app and points Claude Code at the plugin directory:

```yaml
- uses: actions/checkout@v4
  with:
    repository: okteto/okteto-agent-skills
    ref: main # pin to a tag or SHA for reproducible runs
    path: .okteto-agent-skills
```

```yaml
claude_args: |
  --plugin-dir ${{ github.workspace }}/.okteto-agent-skills/plugins/okteto
```

That gives the headless run the same skills (and guard hooks) a developer gets from `/plugin install okteto`. Pin `ref` to a release tag or commit SHA so plugin updates can't change your pipeline's behavior underneath you.

### The teardown policy: `OKTETO_ALLOW_AGENT_DESTROY`

The skill's cleanup rule for autonomous mode is: **never destroy without authorization** — an agent may only run `okteto destroy` / `okteto namespace delete` when the task explicitly authorizes it, a documented cleanup policy exists, or *the environment is ephemeral and owned by the pipeline*. This workflow is the canonical example of that last case — the "explicit cleanup policy" — and it makes the authorization machine-readable:

```yaml
env:
  OKTETO_ALLOW_AGENT_DESTROY: "1"
```

The plugin's guard hook (`plugins/okteto/hooks/guard-okteto.sh`) enforces the skill's rules mechanically: it blocks `okteto up` outright (interactive, would hang the runner) and stops destructive okteto commands to ask for confirmation — unless `OKTETO_ALLOW_AGENT_DESTROY=1|true` is set. Because this pipeline creates the namespace, owns it, and guarantees its teardown, it sets the variable, and the agent can clean up after itself without a human in the loop.

Who destroys what, and when:

| Situation | Who tears down | How |
|---|---|---|
| Run succeeds, PR open for review | Nobody yet | Environment stays up so reviewers can use the preview URL. |
| PR closes (merged or not) | The `cleanup` job | Re-derives the namespace from the PR's head ref and destroys it. |
| Agent decides it cannot complete the task | The agent itself | `okteto destroy` + `okteto namespace delete`, pre-authorized by the env var. |
| Run fails or is cancelled | The `Tear down on failure` step | Same commands, so failed runs never leak environments. |

**Do not set `OKTETO_ALLOW_AGENT_DESTROY` in a developer's local environment or in shared/long-lived contexts.** It exists for pipelines that own their environments end-to-end; everywhere else, the confirmation prompt is the point.

### Security notes

- **The `agent` label is the authorization gate.** Only users with triage access or better can add labels, so random issue authors can't start runs. Keep it that way — don't switch the trigger to something an outsider can set.
- **The issue body is untrusted input.** It's handed to the agent as requirements, and the prompt marks it as data rather than instructions — but prompt injection is never fully solved. The real containment is the tool allowlist plus the label gate.
- **The tool allowlist is deliberately tight.** `--allowedTools` permits `okteto`, `git`, `gh`, `curl`, `jq`, and file edits — nothing else. Builds and tests run *inside the cluster* via `okteto build` / `okteto test`, so the runner needs no language toolchains and the agent needs no broad shell access. Widen the list only as your project demands.
- **PRs created with the workflow's `GITHUB_TOKEN` don't trigger other workflows** (GitHub's recursion guard), so your CI won't run on the agent's PR automatically. If you need that, pass a GitHub App installation token or a PAT as `github_token` instead — see the [claude-code-action setup docs](https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md).

### Tuning

- `--max-turns 50` caps how long the agent can iterate; raise it for large environments or complex issues.
- Pin a model by adding e.g. `--model claude-opus-4-8` to `claude_args`.
- `BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` give `okteto deploy --wait` and `okteto build` room beyond Claude Code's 2-minute default command timeout; scale them with your environment's deploy time, along with the job-level `timeout-minutes`.
