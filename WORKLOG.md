# WORKLOG

## 2026-03-29 — v1.2.0 → v1.2.2: Agentic improvements + project principles

### What was done

**v1.2.0** — Config, history, and 8 agentic improvement tickets (TC-2 through TC-9):
- `~/.config/tavily-cli/config.toml` support (tomllib read, manual TOML write)
- Opt-in history logging with dated JSON hierarchy under `~/.config/tavily-cli/history/`
- `--compact` / `--top N` — agent-friendly compact JSON (answer + top N results, title/url/content only)
- `--answer-only` — print just the AI answer string
- `--urls-only` — one URL per line for piping
- `--max-content N` (extract) — truncate raw_content to N chars per result
- 150KB overflow warning to stderr (prevents LLM context overflow)
- Default `max_results` changed from 20 to 5 for display

**v1.2.1** — Project principles applied:
1. **Get max value**: API always fetches `max_results=20`, `include_raw_content="markdown"`, `include_answer="basic"` regardless of display flags. 1 credit covers everything.
2. **Store what we paid for**: History stores the full 20-result response, not the display-trimmed version.
3. **Cap client-side**: All display limiting (`-n`, `--top`, `--compact`, `--urls-only`, `--answer-only`) is client-side only.
4. **Privacy**: `history_enabled` defaults to `false` — explicit opt-in required.

**v1.2.2** — Help text cleanup + skill/CLAUDE.md updates

### Challenges & lessons

- **Click 8.3 removed `mix_stderr` from CliRunner**: `result.output` is combined stdout+stderr. Use `result.stdout` for JSON parsing in tests.
- **`-n` default=5 silently overrode `--top N`**: When `-n` has a default value in Click, it's always present in kwargs. Changed to `default=None` and resolve to 5 at display time.
- **History `[history]` line pollutes JSON output**: The `click.echo(err=True)` line goes to stderr, but `result.output` in tests includes both. Added `autouse` fixture that isolates `CONFIG_DIR`/`CONFIG_FILE` to temp dirs for all tests.
- **Plow of single-file project must be serial**: All 8 tickets touch `tavily_cli.py`, so parallel agents would cause merge conflicts. Ran sequentially with merge→QA→next cycle.
- **n>20 API behavior is erratic**: Tested via direct SDK calls — `max_results=25` sometimes returns 10, sometimes 20. Conclusion: above 20 is unreliable.
- **Session log analysis drove design**: Analyzed 5,542 real tavily CLI invocations — 74% used default n=20 but agents consumed only 3-5 results, 772 calls used `| jq '.answer'`. This motivated `--answer-only`, `--compact`, and the default change to 5.

### Test count
- Started: 23 tests
- Final: 106 tests (all passing)
