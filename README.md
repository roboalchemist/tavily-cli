# tavily-cli

Command-line interface for the [Tavily](https://tavily.com) AI-powered search API.

## Installation

### Via Homebrew (macOS)

```bash
brew tap roboalchemist/tap
brew install tavily-cli
```

### Via pip

```bash
pip install tavily-python
git clone https://github.com/roboalchemist/tavily-cli.git
cd tavily-cli
make install
```

## Configuration

Set your Tavily API key as an environment variable:

```bash
export TAVILY_API_KEY="tvly-YOUR_API_KEY"
```

Get your free API key at: https://app.tavily.com

## Usage

```
tavily [--api-key KEY] [--format json|text|markdown] [--verbose] <command>
```

### Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--api-key` | `-k` | API key (default: `$TAVILY_API_KEY`) |
| `--format` | `-f` | Output format: `json`, `text`, `markdown` (default: `text`) |
| `--verbose` | `-v` | Debug/verbose output |
| `--help` | `-h` | Show help |

---

## Commands

### `tavily search <query>`

Execute a web search query.

```bash
tavily search "who is Leo Messi?" [options]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--depth` | `-d` | Search depth: `basic` (1 credit), `advanced` (2 credits) |
| `--topic` | `-t` | Topic: `general`, `news`, `finance` |
| `--max-results` | `-n` | Max results (1-20, default: 5) |
| `--time-range` | | Filter by time: `day`, `week`, `month`, `year` |
| `--include-answer` | `-a` | Include LLM-generated answer: `basic` or `advanced` |
| `--include-raw` | `-r` | Include raw page content: `markdown` or `text` |
| `--include-images` | | Include image search results |
| `--include-domains` | | Comma-separated domains to include |
| `--exclude-domains` | | Comma-separated domains to exclude |
| `--country` | | Boost results from country (e.g., `united states`) |

---

### `tavily extract <url> [url...]`

Extract content from one or more URLs.

```bash
tavily extract https://example.com https://example.org [options]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--depth` | `-d` | Extraction depth: `basic`, `advanced` |
| `--output-format` | | Content format: `markdown`, `text` |
| `--include-images` | | Include extracted images |
| `--timeout` | | Timeout in seconds (1-60) |

---

### `tavily crawl <url>`

Crawl a website and extract content from discovered pages.

```bash
tavily crawl https://docs.example.com [options]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--instructions` | `-i` | Natural language crawl instructions |
| `--max-depth` | | Max crawl depth (1-5, default: 1) |
| `--max-breadth` | | Links per page (default: 20) |
| `--limit` | `-n` | Total pages to process (default: 50) |
| `--select-paths` | | Regex patterns for paths to include |
| `--exclude-paths` | | Regex patterns for paths to exclude |
| `--select-domains` | | Regex patterns for domains to include |
| `--exclude-domains` | | Regex patterns for domains to exclude |
| `--no-external` | | Exclude external links |
| `--depth` | `-d` | Extraction depth: `basic`, `advanced` |
| `--include-images` | | Include images in results |
| `--timeout` | | Timeout in seconds (10-150) |

---

### `tavily map <url>`

Generate a site map (URLs only, no content extraction).

```bash
tavily map https://docs.example.com [options]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--instructions` | `-i` | Natural language crawl instructions |
| `--max-depth` | | Max crawl depth (1-5, default: 1) |
| `--max-breadth` | | Links per page (default: 20) |
| `--limit` | `-n` | Total pages to process (default: 50) |
| `--select-paths` | | Regex patterns for paths to include |
| `--exclude-paths` | | Regex patterns for paths to exclude |
| `--select-domains` | | Regex patterns for domains to include |
| `--exclude-domains` | | Regex patterns for domains to exclude |
| `--no-external` | | Exclude external links |
| `--timeout` | | Timeout in seconds (10-150) |

---

### `tavily usage`

Show API key and account usage statistics.

```bash
tavily usage
```

Shows:
- Key usage/limit
- Account plan
- Plan usage/limit
- Pay-as-you-go usage/limit

---

## Examples

```bash
# Simple search
tavily search "best python web frameworks 2025"

# Advanced search with answer
tavily search "climate change impact 2024" -d advanced -a advanced -n 10

# News search
tavily search "AI regulations" -t news --time-range week

# Extract content from URLs
tavily extract https://docs.python.org/3/tutorial/ https://realpython.com/

# Crawl documentation site
tavily crawl https://docs.tavily.com -i "Find Python SDK docs" --limit 20

# Generate site map
tavily map https://example.com --max-depth 2

# Check usage
tavily usage

# JSON output for scripting
tavily search "rust programming" -f json | jq '.results[].url'
```

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

Free tier: 1,000 credits/month

## License

MIT
