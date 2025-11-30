#!/usr/bin/env python3
"""
Tavily CLI - Command-line interface for the Tavily AI search API.
"""

import json
import logging
import os
import sys
from typing import Optional

import click
import requests
from tavily import TavilyClient

logger = logging.getLogger(__name__)

SEARCH_TOPICS = ["general", "news", "finance"]
SEARCH_DEPTHS = ["basic", "advanced"]
TIME_RANGES = ["day", "week", "month", "year", "d", "w", "m", "y"]
OUTPUT_FORMATS = ["json", "text", "markdown"]
CONTENT_FORMATS = ["markdown", "text"]


class TavilyCLI:
    def __init__(self, api_key: str, output_format: str = "text"):
        self.api_key = api_key
        self.client = TavilyClient(api_key=api_key)
        self.output_format = output_format

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

    def display_search_results(self, response: dict) -> None:
        """Display search results in a readable format."""
        if self.output_format == "json":
            click.echo(json.dumps(response, indent=2))
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

    def display_extract_results(self, response: dict) -> None:
        """Display extract results in a readable format."""
        if self.output_format == "json":
            click.echo(json.dumps(response, indent=2))
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

            if is_md:
                click.echo(f"## {i}. {url}\n")
                click.echo(f"{content}\n")
                click.echo("---\n")
            else:
                click.secho(f"{i}. {url}\n", bold=True)
                click.echo(content[:2000])
                if len(content) > 2000:
                    click.echo(f"\n... ({len(content) - 2000} more characters)")
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
            click.echo(json.dumps(response, indent=2))
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
            click.echo(json.dumps(response, indent=2))
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
@click.option("-f", "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="text", help="Output format")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug output")
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx, api_key: str, output_format: str, verbose: bool):
    """Tavily CLI - AI-powered search from the command line.

    Get your free API key at: https://app.tavily.com
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not api_key:
        click.secho("Error: No API key provided.", fg="red", err=True)
        click.echo("Set TAVILY_API_KEY environment variable or use --api-key option.", err=True)
        click.echo("Get your free API key at: https://app.tavily.com", err=True)
        ctx.exit(1)

    ctx.obj = TavilyCLI(api_key=api_key, output_format=output_format)


@cli.command()
@click.argument("query")
@click.option("-d", "--depth", type=click.Choice(SEARCH_DEPTHS), default="basic", help="Search depth (basic=1 credit, advanced=2 credits)")
@click.option("-t", "--topic", type=click.Choice(SEARCH_TOPICS), default="general", help="Search topic")
@click.option("-n", "--max-results", type=click.IntRange(1, 20), default=5, help="Maximum results (1-20)")
@click.option("--time-range", type=click.Choice(TIME_RANGES), help="Filter by time range")
@click.option("-a", "--include-answer", is_flag=False, flag_value="basic", default=None, help="Include LLM answer (basic or advanced)")
@click.option("-r", "--include-raw", is_flag=False, flag_value="markdown", default=None, help="Include raw content (markdown or text)")
@click.option("--include-images", is_flag=True, help="Include image results")
@click.option("--include-domains", callback=parse_list, help="Comma-separated domains to include")
@click.option("--exclude-domains", callback=parse_list, help="Comma-separated domains to exclude")
@click.option("--country", help="Boost results from country")
@pass_cli
def search(
    tavily_cli: TavilyCLI,
    query: str,
    depth: str,
    topic: str,
    max_results: int,
    time_range: Optional[str],
    include_answer: Optional[str],
    include_raw: Optional[str],
    include_images: bool,
    include_domains: Optional[list],
    exclude_domains: Optional[list],
    country: Optional[str],
):
    """Execute a web search query.

    Example: tavily search "who is Leo Messi?" -d advanced -a
    """
    kwargs = {
        "query": query,
        "search_depth": depth,
        "topic": topic,
        "max_results": max_results,
        "include_images": include_images,
    }

    if time_range:
        kwargs["time_range"] = time_range
    if include_answer:
        kwargs["include_answer"] = include_answer if include_answer not in ("true", "True") else True
    if include_raw:
        kwargs["include_raw_content"] = include_raw if include_raw not in ("true", "True") else True
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if country:
        kwargs["country"] = country

    logger.debug(f"Search kwargs: {kwargs}")
    response = tavily_cli.client.search(**kwargs)
    tavily_cli.display_search_results(response)


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("-d", "--depth", type=click.Choice(SEARCH_DEPTHS), default="basic", help="Extraction depth")
@click.option("--output-format", type=click.Choice(CONTENT_FORMATS), default="markdown", help="Content format")
@click.option("--include-images", is_flag=True, help="Include images")
@click.option("--timeout", type=click.FloatRange(1, 60), help="Timeout in seconds (1-60)")
@pass_cli
def extract(
    tavily_cli: TavilyCLI,
    urls: tuple,
    depth: str,
    output_format: str,
    include_images: bool,
    timeout: Optional[float],
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
    response = tavily_cli.client.extract(**kwargs)
    tavily_cli.display_extract_results(response)


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
    response = tavily_cli.client.crawl(**kwargs)
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
    response = tavily_cli.client.map(**kwargs)
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
