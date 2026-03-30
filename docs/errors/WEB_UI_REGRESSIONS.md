# Web UI Regressions

Guardrails for visual and interaction defects in the vanilla frontend (`web/`) that are not primarily API/contract bugs.

Use this with:

- [WEB_DESIGN_TOKENS.md](../features/web/WEB_DESIGN_TOKENS.md)
- [FRONTEND_PATTERNS.md](../practices/FRONTEND_PATTERNS.md)
- [DEFECT_TO_TOOLING.md](../AIbuilding/DEFECT_TO_TOOLING.md)

## Entry template

```markdown
### <short defect title>
- Symptom:
- Surfaces affected:
- Root cause:
- Fix pattern:
- Guardrail location(s):
```

## Known regressions

### Tooltip text not centered in sub-context poster overlays

- Symptom: hover pill labels (for example "Where to watch") appeared vertically misaligned against their dark background in sub-context while looking acceptable in main.
- Surfaces affected: sub-context Movie Hub poster overlays, carousel poster overlays.
- Root cause: pseudo-element tooltip labels inherited high global typography line-height from `body`.
- Fix pattern:
  - Define and use explicit tooltip line-height token (`--media-strip-tooltip-line-height`).
  - Center tooltip labels with `inline-flex` + `align-items: center` + `justify-content: center`.
  - Set icon action controls to `line-height: 1` to avoid local text baseline drift.
- Guardrail location(s):
  - [`web/css/chat.css`](../../web/css/chat.css) (token declaration in media tooltip token block)
  - [`web/css/media.css`](../../web/css/media.css) (overlay action and `::after` tooltip styles)
  - [`.cursor/skills/cinemind-ux-web/SKILL.md`](../../.cursor/skills/cinemind-ux-web/SKILL.md) (cross-surface inheritance check)
