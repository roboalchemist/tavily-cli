# tavily-cli

Command-line interface for the [Tavily](https://tavily.com) AI-powered search API.
Public repo: `~/github/tavily-cli` → https://github.com/roboalchemist/tavily-cli

---

## Project Structure

```
tavily-cli/
├── tavily_cli.py            # Entire CLI — single-file implementation (554 lines)
├── requirements.txt         # Runtime deps: tavily-python, click, requests
├── requirements-dev.txt     # Dev deps: pytest, pytest-mock, ruff
├── Makefile                 # Task runner (install, test, lint, format, clean)
├── tests/
│   ├── __init__.py
│   ├── test_cli.py          # Unit tests (mocked, no API key needed)
│   └── test_e2e.py          # E2E tests (requires TAVILY_API_KEY)
└── .github/
    └── workflows/
        └── bump-tap.yml     # Auto-updates Homebrew formula on release
```

No `pyproject.toml` or `setup.py` — installed manually or via Homebrew.

---

## Architecture

### Core Class: `TavilyCLI`

Wraps `TavilyClient` from `tavily-python` SDK and owns all display logic.

```python
class TavilyCLI:
    def __init__(self, api_key: str, output_format: str = "text")
    def get_usage(self) -> dict          # REST call to api.tavily.com/usage
    def display_search_results(...)      # text / json / markdown rendering
    def display_extract_results(...)
    def display_crawl_results(...)
    def display_map_results(...)
    def display_usage(...)
```

### Click CLI Structure

```
cli (group) [--api-key/-k, --format/-f, --verbose/-v]
├── search  <query>         # Web search
├── extract <url> [url...]  # Content extraction from URLs
├── crawl   <url>           # Spider a site, extract content
├── map     <url>           # Spider a site, return URLs only
└── usage                   # Show API key/account usage stats
```

- Uses `click.make_pass_decorator(TavilyCLI)` to inject the client into commands
- API key comes from `TAVILY_API_KEY` env var or `--api-key` flag
- Three output formats: `text` (default, colored), `json`, `markdown`
- Version: `1.1.1` (hardcoded in `@click.version_option`)

### Helper

```python
def parse_list(ctx, param, value: str) -> Optional[list]  # comma-separated → list
```

---

## Libraries & Patterns

| Library | Version | Role | Docs |
|---------|---------|------|------|
| `click` | >=8.0 | CLI framework (groups, decorators, options, testing) | — |
| `tavily-python` | >=0.5.0 | Tavily SDK (`TavilyClient.search/extract/crawl/map`) | — |
| `requests` | >=2.25 | Direct REST call for `/usage` endpoint | `~/github/llm-code-docs/docs/web-scraped/requests/` |
| `pytest` | >=7.0 | Test runner | `~/github/llm-code-docs/docs/web-scraped/pytest/` |
| `pytest-mock` | >=3.0 | Mocking helpers | — |
| `ruff` | >=0.1 | Linter + formatter | `~/github/llm-code-docs/docs/llms-txt/ruff/` |

> Note: Project uses **click** (not typer). Respect this — do not refactor to typer.

---

## Commands (Quick Reference)

| Command | Key Options |
|---------|------------|
| `search <query>` | `-d basic\|advanced`, `-t general\|news\|finance`, `-n 1-20`, `-a`, `-r`, `--time-range`, `--include-domains`, `--exclude-domains`, `-m` (minimal) |
| `extract <url...>` | `-d basic\|advanced`, `--output-format markdown\|text`, `--include-images`, `--timeout` |
| `crawl <url>` | `-i instructions`, `--max-depth 1-5`, `--max-breadth`, `-n limit`, `--select-paths`, `--exclude-paths`, `--no-external`, `-d`, `--timeout` |
| `map <url>` | `-i instructions`, `--max-depth 1-5`, `--max-breadth`, `-n limit`, `--select-paths`, `--exclude-paths`, `--no-external`, `--timeout` |
| `usage` | (no options) |

---

## Testing

```bash
make test           # All tests (unit + e2e)
make test-unit      # Unit tests only — no API key required
make test-e2e       # E2E tests — requires TAVILY_API_KEY env var

# Direct pytest
pytest tests/test_cli.py -v       # unit (mocked with click.testing.CliRunner)
pytest tests/test_e2e.py -v       # e2e (live API, consumes credits)
```

### Test Structure

- **Unit tests** (`test_cli.py`): Use `click.testing.CliRunner` + `unittest.mock.patch("tavily_cli.TavilyClient")`. Cover all 5 commands, help output, JSON/text formats, parse_list helper.
- **E2E tests** (`test_e2e.py`): Live API calls. Auto-skip if `TAVILY_API_KEY` not set. Tests all commands + output formats.

---

## Linting & Formatting

```bash
make lint       # ruff check + ruff format --check
make format     # ruff format (auto-fix)
```

---

## Installation

### Homebrew (preferred)
```bash
brew tap roboalchemist/tap
brew install tavily-cli
```
Formula: `~/github/homebrew-tap/Formula/tavily-cli.rb`
- Uses Python 3.12, installs deps to `libexec/vendor`, wraps with shell script

### Manual (dev)
```bash
pip install -r requirements.txt
make install
ln -sf $(PWD)/tavily_cli.py /usr/local/bin/tavily
# or: pip install -e .
```

### Dev setup
```bash
make install-dev    # installs runtime + dev deps
```

---

## Releasing

1. Bump version in `tavily_cli.py` → `@click.version_option(version="X.Y.Z")`
2. Create a GitHub release tagged `vX.Y.Z`
3. GitHub Actions (`bump-tap.yml`) auto-updates `~/github/homebrew-tap/Formula/tavily-cli.rb` with new URL + sha256

---

## Configuration

```bash
export TAVILY_API_KEY="tvly-YOUR_API_KEY"   # required
```

Get key at: https://app.tavily.com (free tier: 1,000 credits/month)

---

## API Credits

| Operation | Cost |
|-----------|------|
| Basic search | 1 credit |
| Advanced search | 2 credits |
| Basic extract | 1 credit per 5 URLs |
| Advanced extract | 2 credits per 5 URLs |
| Map | 1 credit per 10 pages |
| Map with instructions | 2 credits per 10 pages |
| Crawl | Map cost + Extract cost |
