# Weekly Planning Lifecycle

Recipe status and planning status are independent. Recipe status describes
whether a dish is family-approved. Planning status describes the operational
state of one weekly menu.

Dry run occurs before this lifecycle and has no persisted status because it
writes no files. Selecting and committing a dry-run option creates the weekly
menu at `draft`.

## States

| Status | Meaning | Exit requirement |
| --- | --- | --- |
| `draft` | Planning is in progress | All weekly artifacts are produced |
| `generated` | Menu, grocery list, and three email drafts exist | Automated validation passes |
| `validated` | Structural and semantic checks pass | Human review occurs |
| `reviewed` | Human review is recorded | Explicit approval |
| `approved` | The week is authorized for delivery | All three emails send successfully |
| `completed` | Delivery is complete | Post-meal feedback is collected |
| `archived` | The week and its feedback are closed | Terminal state |

The normal path is:

`draft -> generated -> validated -> reviewed -> approved -> completed -> archived`

Plan Week drives the active portion of this lifecycle:

1. `Commit Selected` creates the draft and keeps the window open for review.
2. `Generate Review Package` creates the grocery list and three email drafts,
   then advances through `generated` to `validated`.
3. The Menu Summary, Grocery List, Email Drafts, and Raw Markdown views remain
   available for any existing week.
4. `Approve Package` records human review and explicit delivery approval.
5. `Send Approved Emails` uses Gmail SMTP and advances to `completed` only
   after all three drafts are delivered.

The sender enters a Google app password at delivery time. It remains in process
memory only. `delivery-status.json` records each successful message ID so a
retry after partial failure skips messages that already sent.

A week in `generated`, `validated`, `reviewed`, or `approved` may return to
`draft` when changes are requested. The transition must include a reason.
Completed weeks can return to `draft` only for an explicit human-requested
rebuild using the reopen option and after preserving an archival snapshot.
Archived weeks remain terminal.

## Commands

Check a weekly menu:

```powershell
python scripts/menu_status.py check menus/2026/2026-06-29.md
```

Advance a weekly menu:

```powershell
python scripts/menu_status.py transition menus/2026/2026-06-29.md validated --actor Codex --note "All validators passed"
```

Every transition updates the TOML front matter and appends an entry to the
menu's Planning Status History table.
