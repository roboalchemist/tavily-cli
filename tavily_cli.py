#!/usr/bin/env python3
"""
Tavily CLI - Command-line interface for the Tavily AI search API.
"""

import json
import logging
import os
import re
import socket
import sys
import time
import tomllib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import click
import requests
from tavily import TavilyClient

logger = logging.getLogger(__name__)

SEARCH_TOPICS = ["general", "news", "finance"]
SEARCH_DEPTHS = ["basic", "advanced"]
TIME_RANGES = ["day", "week", "month", "year", "d", "w", "m", "y"]
OUTPUT_FORMATS = ["json", "text", "markdown"]
CONTENT_FORMATS = ["markdown", "text"]

# Warn when JSON output exceeds this size — Claude Code's persisted-output threshold
# is ~209KB; 150KB gives a comfortable buffer before truncation kicks in.
CONTEXT_SAFE_OUTPUT_BYTES = 150_000

CONFIG_DIR = os.path.expanduser("~/.config/tavily-cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")


def load_config() -> dict:
    """Load configuration from ~/.config/tavily-cli/config.toml.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.warning("Could not read config file %s: %s", CONFIG_FILE, e)
        return {}


def save_config(config: dict) -> None:
    """Write configuration back to ~/.config/tavily-cli/config.toml.

    Only the keys present in *config* are written; this is a full overwrite.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lines = []
    for key, value in config.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        logger.warning("Could not write config file %s: %s", CONFIG_FILE, e)


def _make_slug(command: str, params: dict) -> str:
    """Generate a short filesystem-safe slug for a history filename."""
    if command == "search":
        raw = params.get("query", "")
    else:
        # extract / crawl / map — use the domain from the first URL
        url_val = params.get("url") or (params.get("urls") or [""])[0]
        raw = urlparse(url_val).netloc or url_val
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-")
    return slug[:40]


class TavilyCLI:
    def __init__(
        self,
        api_key: str,
        output_format: str = "text",
        history_enabled: bool = False,
        no_history: bool = False,
        config: Optional[dict] = None,
    ):
        self.api_key = api_key
        self.client = TavilyClient(api_key=api_key)
        self.output_format = output_format
        self.history_enabled = history_enabled
        self.no_history = no_history
        self.config = config or {}

    def write_history(self, command: str, params: dict, response: dict, latency_ms: int) -> None:
        """Write an API call to the history log under ~/.config/tavily-cli/history/.

        No-ops when history is disabled or --no-history was passed.
        """
        if not self.history_enabled or self.no_history:
            return

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        time_part = now.strftime("%H-%M-%S")

        slug = _make_slug(command, params)
        hostname = socket.gethostname()
        # Sanitize hostname for use in a filename
        safe_host = re.sub(r"[^a-zA-Z0-9._-]", "-", hostname)

        history_dir = os.path.join(CONFIG_DIR, "history", command, year, month, day)
        os.makedirs(history_dir, exist_ok=True)

        filename = f"{time_part}_{slug}_{safe_host}.json"
        filepath = os.path.join(history_dir, filename)

        # Sanitize params — remove api_key if somehow present
        clean_params = {k: v for k, v in params.items() if k != "api_key"}

        envelope = {
            "meta": {
                "timestamp": timestamp,
                "hostname": hostname,
                "command": command,
                "params": clean_params,
                "latency_ms": latency_ms,
            },
            "response": response,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(envelope, f, indent=2)
            logger.debug("History written to %s", filepath)
            click.echo(f"[history] {filepath}", err=True)
        except Exception as e:
            logger.warning("Could not write history file %s: %s", filepath, e)

    def _warn_if_large(self, serialized: str) -> None:
        """Emit a stderr warning when JSON output exceeds the context-safe threshold.

        The warning is written to stderr so stdout remains valid JSON and can be
        piped directly to ``jq`` or other tools without interference.
        """
        size = len(serialized.encode())
        if size > CONTEXT_SAFE_OUTPUT_BYTES:
            kb = size // 1024
            click.echo(
                f"Warning: output is {kb}KB (>{CONTEXT_SAFE_OUTPUT_BYTES // 1024}KB"
                " context-safe limit). Use --compact, -n 5, or --include-raw=false"
                " to reduce size.",
                err=True,
            )

    def get_usage(self) -> dict:
        """Get API usage information via REST API."""
        response = requests.get(
            "https://api.tavily.com/usage",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _print_dict(self, d: dict, indent: int = 0) -> None:
        """Print dictionary with indentation."""
        prefix = "  " * indent
        for key, value in d.items():
            if isinstance(value, dict):
                click.echo(f"{prefix}{click.style(f'{key}:', fg='yellow')}")
                self._print_dict(value, indent + 1)
            elif isinstance(value, list):
                click.echo(f"{prefix}{click.style(f'{key}:', fg='yellow')}")
                for item in value:
                    if isinstance(item, dict):
                        self._print_dict(item, indent + 1)
                        click.echo()
                    else:
                        click.echo(f"{prefix}  - {item}")
            else:
                click.echo(f"{prefix}{click.style(f'{key}:', fg='yellow')} {value}")

    def display_search_results(
        self, response: dict, compact: bool = False, answer_only: bool = False
    ) -> None:
        """Display search results in a readable format.

        When *compact* is True and output format is json, emit a stripped shape:
        ``{"answer": "...", "results": [{"title", "url", "content": first 200 chars}]}``
        instead of the full Tavily response dict.  This keeps output under ~10 KB for
        5 results and is safe for agent consumption without further filtering.

        When *answer_only* is True, emit only the AI-synthesized answer string and return.
        In json format: ``{"answer": "..."}``.  In text/markdown format: the raw answer
        string (stripped), suitable for piping.  Exits non-zero if no answer is present.
        """
        if answer_only:
            answer = response.get("answer", "")
            if not answer:
                click.secho("Error: No answer returned by the API.", fg="red", err=True)
                sys.exit(1)
            if self.output_format == "json":
                click.echo(json.dumps({"answer": answer}))
            elif self.output_format == "markdown":
                click.echo(f"## Answer\n\n{answer.strip()}")
            else:
                click.echo(answer.strip())
            return


        if self.output_format == "json":
            if compact:
                stripped = {
                    "answer": response.get("answer", ""),
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "content": r.get("content", "")[:200],
                        }
                        for r in response.get("results", [])
                    ],
                }
                click.echo(json.dumps(stripped))
            else:
                serialized = json.dumps(response, indent=2)
                self._warn_if_large(serialized)
                click.echo(serialized)
            return

        is_md = self.output_format == "markdown"

        if is_md:
            click.echo(f"# Search: {response.get('query', '')}\n")
        else:
            click.secho(f"Search: {response.get('query', '')}\n", fg="blue", bold=True)

        # Display answer if present
        if "answer" in response and response["answer"]:
            if is_md:
                click.echo(f"## Answer\n\n{response['answer']}\n")
            else:
                click.secho("Answer:", fg="green", bold=True)
                click.echo(f"{response['answer']}\n")

        # Display results
        results = response.get("results", [])
        if is_md:
            click.echo(f"## Results ({len(results)})\n")
        else:
            click.secho(f"Results ({len(results)}):\n", fg="yellow", bold=True)

        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "")
            score = result.get("score", 0)

            if is_md:
                click.echo(f"### {i}. [{title}]({url})")
                click.echo(f"*Score: {score:.2f}*\n")
                click.echo(f"{content}\n")
            else:
                click.secho(f"{i}. {title}", bold=True)
                click.secho(f"   {url}", fg="blue")
                click.echo(f"   Score: {score:.2f}")
                click.echo(f"   {content[:200]}{'...' if len(content) > 200 else ''}\n")

        # Display images if present
        images = response.get("images", [])
        if images:
            if is_md:
                click.echo(f"## Images ({len(images)})\n")
                for img in images:
                    if isinstance(img, dict):
                        click.echo(f"- ![{img.get('description', '')}]({img.get('url', '')})")
                    else:
                        click.echo(f"- {img}")
            else:
                click.secho(f"Images ({len(images)}):", fg="yellow", bold=True)
                for img in images:
                    if isinstance(img, dict):
                        click.echo(f"  - {img.get('url', '')} - {img.get('description', '')}")
                    else:
                        click.echo(f"  - {img}")

        # Display response time
        if "response_time" in response:
            if is_md:
                click.echo(f"\n*Response time: {response['response_time']:.2f}s*")
            else:
                click.secho(f"\nResponse time: {response['response_time']:.2f}s", fg="bright_black")

    def display_urls_only(self, response: dict) -> None:
        """Display only the URLs from search results.

        JSON: ``{"urls": ["https://...", ...]}``
        Text: one URL per line
        Markdown: bulleted list of URLs
        """
        urls = [r["url"] for r in response.get("results", []) if r.get("url")]

        if self.output_format == "json":
            click.echo(json.dumps({"urls": urls}))
        elif self.output_format == "markdown":
            click.echo("\n".join(f"- {url}" for url in urls))
        else:
            click.echo("\n".join(urls))

    def display_extract_results(self, response: dict, max_content: Optional[int] = None) -> None:
        """Display extract results in a readable format."""
        if self.output_format == "json":
            if max_content is not None:
                # Deep-copy the response to avoid mutating the original, then truncate
                response = json.loads(json.dumps(response))
                for result in response.get("results", []):
                    if "raw_content" in result and result["raw_content"]:
                        result["raw_content"] = result["raw_content"][:max_content]
            serialized = json.dumps(response, indent=2)
            self._warn_if_large(serialized)
            click.echo(serialized)
            return

        is_md = self.output_format == "markdown"

        if is_md:
            click.echo("# Extracted Content\n")
        else:
            click.secho("Extracted Content\n", fg="blue", bold=True)

        results = response.get("results", [])
        for i, result in enumerate(results, 1):
            url = result.get("url", "")
            content = result.get("raw_content", "")

            # Apply --max-content truncation (client-side display only)
            truncated = False
            if max_content is not None and content and len(content) > max_content:
                content = content[:max_content]
                truncated = True

            if is_md:
                click.echo(f"## {i}. {url}\n")
                click.echo(f"{content}")
                if truncated:
                    click.echo(f"\n... [truncated at {max_content} chars]")
                click.echo("\n---\n")
            else:
                click.secho(f"{i}. {url}\n", bold=True)
                click.echo(content)
                if truncated:
                    click.echo(f"\n... [truncated at {max_content} chars]")
                click.echo("\n" + "-" * 60 + "\n")

        # Display failed results
        failed = response.get("failed_results", [])
        if failed:
            if is_md:
                click.echo("## Failed URLs\n")
                for f in failed:
                    click.echo(f"- {f.get('url', '')}: {f.get('error', 'Unknown error')}")
            else:
                click.secho("Failed URLs:", fg="red", bold=True)
                for f in failed:
                    click.echo(f"  - {f.get('url', '')}: {f.get('error', 'Unknown error')}")

        if "response_time" in response:
            if is_md:
                click.echo(f"\n*Response time: {response['response_time']:.2f}s*")
            else:
                click.secho(f"\nResponse time: {response['response_time']:.2f}s", fg="bright_black")

    def display_crawl_results(self, response: dict) -> None:
        """Display crawl results in a readable format."""
        if self.output_format == "json":
            serialized = json.dumps(response, indent=2)
            self._warn_if_large(serialized)
            click.echo(serialized)
            return

        is_md = self.output_format == "markdown"
        base_url = response.get("base_url", "")

        if is_md:
            click.echo(f"# Crawl Results: {base_url}\n")
        else:
            click.secho(f"Crawl Results: {base_url}\n", fg="blue", bold=True)

        results = response.get("results", [])
        if is_md:
            click.echo(f"## Pages Crawled ({len(results)})\n")
        else:
            click.secho(f"Pages Crawled ({len(results)}):\n", fg="yellow", bold=True)

        for i, result in enumerate(results, 1):
            url = result.get("url", "")
            content = result.get("raw_content", "")

            if is_md:
                click.echo(f"### {i}. {url}\n")
                preview = content[:500] if content else ""
                click.echo(f"{preview}{'...' if len(content) > 500 else ''}\n")
            else:
                click.secho(f"{i}. {url}", bold=True)
                preview = content[:300] if content else ""
                click.echo(f"   {preview}{'...' if len(content) > 300 else ''}\n")

        if "response_time" in response:
            if is_md:
                click.echo(f"\n*Response time: {response['response_time']:.2f}s*")
            else:
                click.secho(f"\nResponse time: {response['response_time']:.2f}s", fg="bright_black")

    def display_map_results(self, response: dict) -> None:
        """Display map results in a readable format."""
        if self.output_format == "json":
            serialized = json.dumps(response, indent=2)
            self._warn_if_large(serialized)
            click.echo(serialized)
            return

        is_md = self.output_format == "markdown"
        base_url = response.get("base_url", "")
        results = response.get("results", [])

        if is_md:
            click.echo(f"# Site Map: {base_url}\n")
            click.echo(f"## URLs Found ({len(results)})\n")
            for url in results:
                click.echo(f"- {url}")
        else:
            click.secho(f"Site Map: {base_url}\n", fg="blue", bold=True)
            click.secho(f"URLs Found ({len(results)}):\n", fg="yellow", bold=True)
            for url in results:
                click.echo(f"  {url}")

        if "response_time" in response:
            if is_md:
                click.echo(f"\n*Response time: {response['response_time']:.2f}s*")
            else:
                click.secho(f"\nResponse time: {response['response_time']:.2f}s", fg="bright_black")

    def display_usage(self, response: dict) -> None:
        """Display usage information."""
        if self.output_format == "json":
            click.echo(json.dumps(response, indent=2))
            return

        is_md = self.output_format == "markdown"

        if is_md:
            click.echo("# API Usage\n")
        else:
            click.secho("API Usage\n", fg="blue", bold=True)

        key_info = response.get("key", {})
        account_info = response.get("account", {})

        if is_md:
            click.echo("## API Key")
            click.echo(f"- **Usage:** {key_info.get('usage', 0)}")
            limit = key_info.get('limit')
            click.echo(f"- **Limit:** {limit if limit else 'Unlimited'}\n")

            click.echo("## Account")
            click.echo(f"- **Plan:** {account_info.get('current_plan', 'Unknown')}")
            click.echo(f"- **Plan Usage:** {account_info.get('plan_usage', 0)} / {account_info.get('plan_limit', 0)}")
            click.echo(f"- **PayGo Usage:** {account_info.get('paygo_usage', 0)} / {account_info.get('paygo_limit', 0)}")
        else:
            click.secho("API Key:", fg="yellow", bold=True)
            click.echo(f"  Usage: {key_info.get('usage', 0)}")
            limit = key_info.get('limit')
            click.echo(f"  Limit: {limit if limit else 'Unlimited'}\n")

            click.secho("Account:", fg="yellow", bold=True)
            click.echo(f"  Plan: {account_info.get('current_plan', 'Unknown')}")
            click.echo(f"  Plan Usage: {account_info.get('plan_usage', 0)} / {account_info.get('plan_limit', 0)}")
            click.echo(f"  PayGo Usage: {account_info.get('paygo_usage', 0)} / {account_info.get('paygo_limit', 0)}")


def parse_list(ctx, param, value: str) -> Optional[list]:
    """Parse comma-separated string into list."""
    if not value:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]


# Store the CLI instance in click context
pass_cli = click.make_pass_decorator(TavilyCLI, ensure=True)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-k", "--api-key", envvar="TAVILY_API_KEY", help="Tavily API key (default: $TAVILY_API_KEY)")
@click.option("-f", "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default=None, help="Output format")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug output")
@click.option("--no-history", is_flag=True, default=False, help="Skip writing history for this invocation")
@click.version_option(version="1.2.1")
@click.pass_context
def cli(ctx, api_key: str, output_format: Optional[str], verbose: bool, no_history: bool):
    """Tavily CLI - AI-powered search from the command line.

    Get your free API key at: https://app.tavily.com
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load config file and apply defaults (CLI flag > env var > config > hardcoded default)
    config = load_config()

    if not api_key:
        api_key = config.get("api_key")

    if output_format is None:
        output_format = config.get("default_format", "text")

    history_enabled = config.get("history_enabled", False)

    if not api_key:
        click.secho("Error: No API key provided.", fg="red", err=True)
        click.echo("Set TAVILY_API_KEY environment variable or use --api-key option.", err=True)
        click.echo("Get your free API key at: https://app.tavily.com", err=True)
        ctx.exit(1)

    ctx.obj = TavilyCLI(
        api_key=api_key,
        output_format=output_format,
        history_enabled=history_enabled,
        no_history=no_history,
        config=config,
    )


@cli.command()
@click.argument("query")
@click.option("-m", "--minimal", is_flag=True, help="Minimal output for small context windows (5 results, no raw content, no images)")
@click.option("--answer-only", is_flag=True, default=False, help="Print only the AI answer (forces advanced answer).")
@click.option("--compact", is_flag=True, default=False, help="Agent-friendly compact JSON: answer + top N results (title/url/content only). Implies --top 5.")
@click.option("--top", "top_n", type=click.IntRange(min=1), default=None, help="Return top N results (default 5 when --compact is set). Implies --compact.")
@click.option("-d", "--depth", type=click.Choice(SEARCH_DEPTHS), default=None, help="Search depth (basic=1 credit, advanced=2 credits)")
@click.option("-t", "--topic", type=click.Choice(SEARCH_TOPICS), default=None, help="Search topic")
@click.option("-n", "--max-results", type=click.IntRange(min=1), default=None, help="Maximum results to display (default: 5). API always fetches 20.")
@click.option("--time-range", type=click.Choice(TIME_RANGES), help="Filter by time range")
@click.option("-a", "--advanced-answer", "advanced_answer", is_flag=True, default=False, help="Use advanced AI answer instead of basic (basic included by default, both free with search).")
@click.option("-r", "--include-raw", is_flag=False, flag_value="markdown", default="markdown", help="Raw content: markdown (default), text, or --include-raw=false to disable. Free with search.")
@click.option("--include-images/--no-images", default=None, help="Include image results (free with search)")
@click.option("--include-domains", callback=parse_list, help="Comma-separated domains to include")
@click.option("--exclude-domains", callback=parse_list, help="Comma-separated domains to exclude")
@click.option("--country", help="Boost results from country")
@click.option("--urls-only", "urls_only", is_flag=True, default=False, help="Print only URLs, one per line.")
@pass_cli
def search(
    tavily_cli: TavilyCLI,
    query: str,
    minimal: bool,
    answer_only: bool,
    compact: bool,
    top_n: Optional[int],
    depth: Optional[str],
    topic: Optional[str],
    max_results: Optional[int],
    time_range: Optional[str],
    advanced_answer: bool,
    include_raw: Optional[str],
    include_images: Optional[bool],
    include_domains: Optional[list],
    exclude_domains: Optional[list],
    country: Optional[str],
    urls_only: bool,
):
    """Execute a web search query.

    Example: tavily search "who is Leo Messi?"
    Example: tavily search "who is Leo Messi?" --answer-only  # answer string only
    Example: tavily search "python frameworks" -m  # minimal output
    Example: tavily search "python frameworks" --compact  # agent-friendly JSON
    Example: tavily search "python frameworks" --top 3  # compact with 3 results
    Example: tavily search "python frameworks" --urls-only  # URLs only, one per line
    """
    # --top N implies --compact
    if top_n is not None:
        compact = True

    # Apply config defaults then hardcoded defaults (CLI flag > config > hardcoded)
    depth = depth or tavily_cli.config.get("default_depth", "basic")
    topic = topic or tavily_cli.config.get("default_topic", "general")

    # Determine display limits (client-side only — never affects what we fetch)
    if answer_only:
        display_max = 0  # results irrelevant, only answer shown
    else:
        display_max = max_results or top_n or tavily_cli.config.get("default_max_results") or 5

    # Principle: always fetch the maximum the API will give for 1 credit.
    # 20 results + raw content (markdown) + basic answer are all free with a basic search.
    # Display is capped client-side; the full response goes to history.
    include_answer = "advanced" if (answer_only or advanced_answer) else "basic"
    kwargs = {
        "query": query,
        "search_depth": depth,
        "topic": topic,
        "max_results": 20,
        "include_answer": include_answer,
        "include_raw_content": "markdown",
        "include_images": include_images if include_images is not None else True,
    }
    if time_range:
        kwargs["time_range"] = time_range
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if country:
        kwargs["country"] = country

    logger.debug(f"Search kwargs: {kwargs}")
    t0 = time.time()
    response = tavily_cli.client.search(**kwargs)
    latency_ms = int((time.time() - t0) * 1000)
    tavily_cli.write_history("search", kwargs, response, latency_ms)

    # Trim results client-side to the requested display count
    if "results" in response:
        display_response = dict(response, results=response["results"][:display_max]) if display_max else response
    else:
        display_response = response

    if urls_only:
        tavily_cli.display_urls_only(display_response)
    else:
        tavily_cli.display_search_results(display_response, compact=compact, answer_only=answer_only)


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("-d", "--depth", type=click.Choice(SEARCH_DEPTHS), default="basic", help="Extraction depth")
@click.option("--output-format", type=click.Choice(CONTENT_FORMATS), default="markdown", help="Content format")
@click.option("--include-images", is_flag=True, help="Include images")
@click.option("--timeout", type=click.FloatRange(1, 60), help="Timeout in seconds (1-60)")
@click.option("--max-content", type=click.IntRange(min=1), default=None, help="Truncate raw_content to N characters per URL (client-side display only)")
@pass_cli
def extract(
    tavily_cli: TavilyCLI,
    urls: tuple,
    depth: str,
    output_format: str,
    include_images: bool,
    timeout: Optional[float],
    max_content: Optional[int],
):
    """Extract content from one or more URLs.

    Example: tavily extract https://example.com https://example.org
    """
    kwargs = {
        "urls": list(urls),
        "extract_depth": depth,
        "include_images": include_images,
    }

    if timeout:
        kwargs["timeout"] = timeout

    logger.debug(f"Extract kwargs: {kwargs}")
    t0 = time.time()
    response = tavily_cli.client.extract(**kwargs)
    latency_ms = int((time.time() - t0) * 1000)
    tavily_cli.write_history("extract", kwargs, response, latency_ms)
    tavily_cli.display_extract_results(response, max_content=max_content)


@cli.command()
@click.argument("url")
@click.option("-i", "--instructions", help="Natural language crawl instructions")
@click.option("--max-depth", type=click.IntRange(1, 5), default=1, help="Max crawl depth (1-5)")
@click.option("--max-breadth", type=int, default=20, help="Links per page")
@click.option("-n", "--limit", type=int, default=50, help="Total pages to process")
@click.option("--select-paths", callback=parse_list, help="Comma-separated regex patterns for paths to include")
@click.option("--exclude-paths", callback=parse_list, help="Comma-separated regex patterns for paths to exclude")
@click.option("--select-domains", callback=parse_list, help="Comma-separated regex patterns for domains to include")
@click.option("--exclude-domains", callback=parse_list, help="Comma-separated regex patterns for domains to exclude")
@click.option("--no-external", is_flag=True, help="Exclude external links")
@click.option("-d", "--depth", type=click.Choice(SEARCH_DEPTHS), default="basic", help="Extraction depth")
@click.option("--include-images", is_flag=True, help="Include images")
@click.option("--timeout", type=click.FloatRange(10, 150), help="Timeout in seconds (10-150)")
@pass_cli
def crawl(
    tavily_cli: TavilyCLI,
    url: str,
    instructions: Optional[str],
    max_depth: int,
    max_breadth: int,
    limit: int,
    select_paths: Optional[list],
    exclude_paths: Optional[list],
    select_domains: Optional[list],
    exclude_domains: Optional[list],
    no_external: bool,
    depth: str,
    include_images: bool,
    timeout: Optional[float],
):
    """Crawl a website and extract content from discovered pages.

    Example: tavily crawl https://docs.example.com -i "Find API docs" --limit 20
    """
    kwargs = {
        "url": url,
        "max_depth": max_depth,
        "max_breadth": max_breadth,
        "limit": limit,
        "allow_external": not no_external,
        "extract_depth": depth,
        "include_images": include_images,
    }

    if instructions:
        kwargs["instructions"] = instructions
    if select_paths:
        kwargs["select_paths"] = select_paths
    if exclude_paths:
        kwargs["exclude_paths"] = exclude_paths
    if select_domains:
        kwargs["select_domains"] = select_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if timeout:
        kwargs["timeout"] = timeout

    logger.debug(f"Crawl kwargs: {kwargs}")
    t0 = time.time()
    response = tavily_cli.client.crawl(**kwargs)
    latency_ms = int((time.time() - t0) * 1000)
    tavily_cli.write_history("crawl", kwargs, response, latency_ms)
    tavily_cli.display_crawl_results(response)


@cli.command("map")
@click.argument("url")
@click.option("-i", "--instructions", help="Natural language crawl instructions")
@click.option("--max-depth", type=click.IntRange(1, 5), default=1, help="Max crawl depth (1-5)")
@click.option("--max-breadth", type=int, default=20, help="Links per page")
@click.option("-n", "--limit", type=int, default=50, help="Total pages to process")
@click.option("--select-paths", callback=parse_list, help="Comma-separated regex patterns for paths to include")
@click.option("--exclude-paths", callback=parse_list, help="Comma-separated regex patterns for paths to exclude")
@click.option("--select-domains", callback=parse_list, help="Comma-separated regex patterns for domains to include")
@click.option("--exclude-domains", callback=parse_list, help="Comma-separated regex patterns for domains to exclude")
@click.option("--no-external", is_flag=True, help="Exclude external links")
@click.option("--timeout", type=click.FloatRange(10, 150), help="Timeout in seconds (10-150)")
@pass_cli
def map_cmd(
    tavily_cli: TavilyCLI,
    url: str,
    instructions: Optional[str],
    max_depth: int,
    max_breadth: int,
    limit: int,
    select_paths: Optional[list],
    exclude_paths: Optional[list],
    select_domains: Optional[list],
    exclude_domains: Optional[list],
    no_external: bool,
    timeout: Optional[float],
):
    """Generate a site map (URLs only, no content extraction).

    Example: tavily map https://example.com --max-depth 2
    """
    kwargs = {
        "url": url,
        "max_depth": max_depth,
        "max_breadth": max_breadth,
        "limit": limit,
        "allow_external": not no_external,
    }

    if instructions:
        kwargs["instructions"] = instructions
    if select_paths:
        kwargs["select_paths"] = select_paths
    if exclude_paths:
        kwargs["exclude_paths"] = exclude_paths
    if select_domains:
        kwargs["select_domains"] = select_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if timeout:
        kwargs["timeout"] = timeout

    logger.debug(f"Map kwargs: {kwargs}")
    t0 = time.time()
    response = tavily_cli.client.map(**kwargs)
    latency_ms = int((time.time() - t0) * 1000)
    tavily_cli.write_history("map", kwargs, response, latency_ms)
    tavily_cli.display_map_results(response)


@cli.command()
@pass_cli
def usage(tavily_cli: TavilyCLI):
    """Show API key and account usage statistics."""
    response = tavily_cli.get_usage()
    tavily_cli.display_usage(response)


def main():
    cli(prog_name="tavily")


if __name__ == "__main__":
    main()
