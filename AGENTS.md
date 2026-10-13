# Daily Codex usage safeguard

The user limits this project to 8 percentage points of their weekly Codex allowance per calendar day in America/Denver. This takes priority over completing the goal or automatic continuation.

Before substantive work on every user turn and automatic goal continuation, and at least every five minutes during work (also before a large work batch), read the current weekly window through `mcp__codex_app__get_usage_limits`. Prefer `rateLimitsByLimitId.codex`, otherwise `rateLimits`; select the window with `windowDurationMins == 10080`. Pass only its `usedPercent` and `resetsAt` to `tools/check_daily_usage.py` using the bundled Python and JSON on stdin. Do not use goal token counts as weekly usage.

Example input: `{"usedPercent":5,"resetsAt":1792509446}`. The ledger is `.workspace/daily-codex-usage.json`, shared by all chats in this checkout. Never delete, reinitialize or change it to gain more allowance. Initial setup has already been performed; do not use `--initialize` again. Fresh/missing/corrupt state, unavailable usage, an account/window change, or a meter decrease must stop work rather than grant fresh allowance. An uncertain reset stops work for the rest of that local day.

The helper returns `STOP` (exit 2) at 7 reported percentage points consumed since the day's first observation, reserving 1 point for meter rounding, polling delay and shutdown. The requested cap remains 8 points; this is a conservative best-effort guard, not an enforced account quota. Usage from other chats counts conservatively because the meter is account-wide. Today's first baseline was 5% on October 13, 2026; earlier usage today is unknown.

On STOP or an unavailable check: stop substantive work immediately, preserve files, call `update_goal(status="paused")` if this chat has an active goal, and briefly report the daily pause and next Denver date. The user has explicitly authorized this conditional pause. Do not mark the goal complete, buy credits, redeem usage resets, spawn work elsewhere, or create wakeup automations to bypass the cap. An ordinary 'continue' on the same day does not override it. On a later day, when the user starts work again, run the check to establish that day's baseline; unused allowance does not carry over. Do not resume or wake up automatically.

# Git workflow

Create local Git commits at coherent implementation milestones after appropriate checks. The user has requested habitual commits; do not ask again for routine local commits.

Keep commits focused on project source, tests, launchers and documentation. Exclude local runtimes, generated application bundles, working aircraft models and temporary diagnostic evidence.

Describe validation and unresolved failures candidly. Do not push commits unless the user requests it.
