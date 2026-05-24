# Contributing to GCP Ironclad

Thanks for considering a contribution. This project tries to be welcoming to GCP / Claude Code users — especially those who've been burned by surprise bills.

## Ways to help

- **Use it and file issues.** Tell us what didn't work, what was confusing, what you expected vs. what happened.
- **Code:** see the *Help wanted* list in the README. Skills are Markdown playbooks; the MCP is Python.
- **Docs:** screenshots / recordings of a real run (anonymized) help newcomers see what they're getting.
- **Risk-classifier examples:** a corpus of anonymized `gcloud services api-keys list` outputs helps tune the heuristics.

## Development setup

```bash
git clone https://github.com/<your-fork>/gcp-ironclad.git
cd gcp-ironclad

# MCP server — Python, has unit tests
cd mcp/gcp-finops
pip install -e ".[dev]"
pytest -v

# Skills are Markdown — no build step. Edit `skills/<name>/SKILL.md` directly.
# For local testing, symlink them into ~/.claude/skills/ (see README "Install" section).
```

## Pull request guidelines

- **One topic per PR.** Mixed PRs are hard to review.
- **For `skills/*/SKILL.md` changes:** walk through a dry-run by hand to confirm the playbook still produces a valid `*.json` matching `output.schema.json`.
- **For `mcp/gcp-finops` changes:** run `pytest -v` and include new tests if you're adding a tool.
- **For changes to safety behavior** (the auto-apply matrix in `gcp-spend-guardrails` and `gcp-key-restrictions`): include a short rationale in the PR description. *Be conservative.* A skill that breaks production is worse than one that flags an action for human review.

## Style

- **Skills:** be explicit about safety gates. Every APPLY action must document its "skip" / "flagged" conditions in the SKILL.md.
- **MCP tools:** small, focused functions; one tool = one purpose. Type hints, docstrings.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) style is appreciated but not enforced.

## Things we are *not* trying to do (yet)

We deliberately scope this project narrowly so it stays trustworthy. The following are out of scope for v1 (but PRs that introduce them as opt-in features are welcome):

- Auto-deleting credentials (always flag-for-review).
- Modifying IAM (org, project, billing-account).
- Closing billing accounts.
- Cross-org / multi-tenant operation.
- Anything that requires network egress beyond GCP itself.

## Code of conduct

Be kind. Assume good intent. Help newcomers.

## License

By contributing, you agree your contributions will be MIT-licensed.
