# Defect To Tooling Loop

Use this playbook when a bug fix should become a repeatable guardrail for future AI-assisted work.

This is not automatic model self-learning. The loop is a disciplined update process:

1. Fix the defect.
2. Classify the defect.
3. Update the right mechanism(s) in the same change or immediate follow-up.
4. Cross-link the result so future agents can discover it quickly.

## When to use

Apply this flow after you understand a user-visible regression and the root cause, especially when the same class of issue could recur.

## Classification matrix

| Defect type | Typical propagation |
|-------------|---------------------|
| Vanilla web / CSS / cross-surface visual drift | Update [`.cursor/skills/cinemind-ux-web/SKILL.md`](../../.cursor/skills/cinemind-ux-web/SKILL.md), [WEB_DESIGN_TOKENS.md](../features/web/WEB_DESIGN_TOKENS.md), and optionally [`.cursor/rules/web-frontend.mdc`](../../.cursor/rules/web-frontend.mdc) if it is a strict guardrail. |
| Hub / sub-context / contract behavior | Update [MOVIE_HUB_AND_SUBCONTEXT.md](../errors/MOVIE_HUB_AND_SUBCONTEXT.md) and, when visual-only, [WEB_UI_REGRESSIONS.md](../errors/WEB_UI_REGRESSIONS.md). |
| Cursor meta-tooling workflow gaps | Update [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md), [`.cursor/skills/cinemind-ai-building/SKILL.md`](../../.cursor/skills/cinemind-ai-building/SKILL.md), and index docs in this folder. |

## Defect entry template

Use this short format in the target doc.

```markdown
### <short defect title>
- Symptom:
- Surfaces affected (main, sub-hub, projects, drawer, modal):
- Root cause:
- Fix applied:
- Tooling delta (files updated so this is less likely next time):
```

## Example: sub-context tooltip text misalignment

- Symptom: hover pill text ("Where to watch") looked vertically off-center in sub-context while looking acceptable on main.
- Surfaces affected: sub-context Movie Hub poster overlays, carousel overlays.
- Root cause: tooltip pseudo-elements inherited high `line-height` from global typography context.
- Fix applied: explicit tooltip line-height token and flex centering on pseudo-elements / icon actions in poster overlay styles.
- Tooling delta:
  - Added guidance to [WEB_DESIGN_TOKENS.md](../features/web/WEB_DESIGN_TOKENS.md) for pseudo-element inheritance checks.
  - Added a workflow bullet to [`.cursor/skills/cinemind-ux-web/SKILL.md`](../../.cursor/skills/cinemind-ux-web/SKILL.md).
  - Logged the pattern in [WEB_UI_REGRESSIONS.md](../errors/WEB_UI_REGRESSIONS.md).

## Verification checklist

- Confirm the user-facing bug is fixed in affected surfaces.
- Confirm at least one mechanism update exists (skill, rule, feature doc, or errors guardrail).
- Confirm index links are updated so agents can discover the new guidance.
- If only docs / `.cursor` files changed, remember hooks do not run related pytest automatically. Run targeted checks manually when needed.
- After scoped fixes (`src/`, `web/`, scenario YAML under `tests/fixtures/scenarios/`, etc.), the `track-scoped-work` hook records **path signals** under `docs/session_logs/.tracking/` (gitignored). Turn that into a polished entry with `python scripts/session_log_draft_from_signals.py` (see [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md) and [SESSION_LOGS.md](SESSION_LOGS.md)).

## Related

- [README.md](README.md)
- [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md)
- [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md)
- [SESSION_LOGS.md](SESSION_LOGS.md)
- [WEB_DESIGN_TOKENS.md](../features/web/WEB_DESIGN_TOKENS.md)
- [Errors & Guardrails](../errors/README.md)
