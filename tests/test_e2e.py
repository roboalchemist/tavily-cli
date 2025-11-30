"""
End-to-end tests for tavily-cli using live API.

These tests require a valid TAVILY_API_KEY environment variable.
They consume API credits, so use sparingly.
"""

import json
import os

import pytest
from click.testing import CliRunner

from tavily_cli import cli


# Skip all tests if no API key is available
pytestmark = pytest.mark.skipif(
    not os.environ.get("TAVILY_API_KEY"),
    reason="TAVILY_API_KEY not set"
)


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


class TestSearchE2E:
    """End-to-end tests for search command."""

    def test_search_basic(self, runner):
        """Test basic search returns results."""
        result = runner.invoke(cli, ["search", "Python programming language", "-n", "3"])
        assert result.exit_code == 0
        assert "Results" in result.output
        assert "python" in result.output.lower()

    def test_search_with_answer(self, runner):
        """Test search with LLM answer."""
        result = runner.invoke(cli, ["search", "What is 2+2?", "-a", "-n", "2"])
        assert result.exit_code == 0
        assert "Answer:" in result.output

    def test_search_news_topic(self, runner):
        """Test search with news topic."""
        result = runner.invoke(cli, ["search", "technology news", "-t", "news", "-n", "3"])
        assert result.exit_code == 0
        assert "Results" in result.output

    def test_search_advanced_depth(self, runner):
        """Test search with advanced depth."""
        result = runner.invoke(cli, ["search", "machine learning", "-d", "advanced", "-n", "2"])
        assert result.exit_code == 0
        assert "Results" in result.output

    def test_search_json_output(self, runner):
        """Test search with JSON output format."""
        result = runner.invoke(cli, ["-f", "json", "search", "test query", "-n", "2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "query" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_markdown_output(self, runner):
        """Test search with markdown output format."""
        result = runner.invoke(cli, ["-f", "markdown", "search", "test query", "-n", "2"])
        assert result.exit_code == 0
        assert "# Search:" in result.output

    def test_search_with_domain_filter(self, runner):
        """Test search with domain inclusion."""
        result = runner.invoke(
            cli,
            ["search", "Python documentation", "--include-domains", "python.org", "-n", "3"]
        )
        assert result.exit_code == 0
        assert "Results" in result.output


class TestExtractE2E:
    """End-to-end tests for extract command."""

    def test_extract_single_url(self, runner):
        """Test extracting content from a single URL."""
        result = runner.invoke(cli, ["extract", "https://example.com"])
        assert result.exit_code == 0
        assert "Extracted Content" in result.output
        assert "example.com" in result.output.lower()

    def test_extract_multiple_urls(self, runner):
        """Test extracting content from multiple URLs."""
        result = runner.invoke(
            cli,
            ["extract", "https://example.com", "https://example.org"]
        )
        assert result.exit_code == 0
        assert "Extracted Content" in result.output

    def test_extract_json_output(self, runner):
        """Test extract with JSON output."""
        result = runner.invoke(cli, ["-f", "json", "extract", "https://example.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_extract_advanced_depth(self, runner):
        """Test extract with advanced depth."""
        result = runner.invoke(cli, ["extract", "https://example.com", "-d", "advanced"])
        assert result.exit_code == 0
        assert "Extracted Content" in result.output


class TestMapE2E:
    """End-to-end tests for map command."""

    def test_map_basic(self, runner):
        """Test basic site mapping."""
        result = runner.invoke(cli, ["map", "https://example.com", "--limit", "5"])
        assert result.exit_code == 0
        assert "Site Map:" in result.output
        assert "URLs Found" in result.output

    def test_map_with_depth(self, runner):
        """Test map with max depth."""
        result = runner.invoke(
            cli,
            ["map", "https://docs.tavily.com", "--max-depth", "1", "--limit", "5"]
        )
        assert result.exit_code == 0
        assert "Site Map:" in result.output

    def test_map_json_output(self, runner):
        """Test map with JSON output."""
        result = runner.invoke(
            cli,
            ["-f", "json", "map", "https://example.com", "--limit", "5"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "base_url" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_map_no_external(self, runner):
        """Test map excluding external links."""
        result = runner.invoke(
            cli,
            ["map", "https://example.com", "--no-external", "--limit", "5"]
        )
        assert result.exit_code == 0
        assert "Site Map:" in result.output


class TestCrawlE2E:
    """End-to-end tests for crawl command."""

    def test_crawl_basic(self, runner):
        """Test basic crawl."""
        result = runner.invoke(
            cli,
            ["crawl", "https://example.com", "--limit", "2"],
            catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "Crawl Results:" in result.output

    def test_crawl_with_instructions(self, runner):
        """Test crawl with natural language instructions."""
        result = runner.invoke(
            cli,
            ["crawl", "https://docs.tavily.com", "-i", "Find API documentation", "--limit", "3"]
        )
        assert result.exit_code == 0
        assert "Crawl Results:" in result.output

    def test_crawl_json_output(self, runner):
        """Test crawl with JSON output."""
        result = runner.invoke(
            cli,
            ["-f", "json", "crawl", "https://example.com", "--limit", "2"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "base_url" in data
        assert "results" in data


class TestUsageE2E:
    """End-to-end tests for usage command."""

    def test_usage_text(self, runner):
        """Test usage command with text output."""
        result = runner.invoke(cli, ["usage"])
        assert result.exit_code == 0
        assert "API Usage" in result.output
        assert "API Key:" in result.output
        assert "Account:" in result.output
        assert "Plan:" in result.output

    def test_usage_json(self, runner):
        """Test usage command with JSON output."""
        result = runner.invoke(cli, ["-f", "json", "usage"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "key" in data
        assert "account" in data
        assert "usage" in data["key"]
        assert "current_plan" in data["account"]

    def test_usage_markdown(self, runner):
        """Test usage command with markdown output."""
        result = runner.invoke(cli, ["-f", "markdown", "usage"])
        assert result.exit_code == 0
        assert "# API Usage" in result.output
        assert "## API Key" in result.output
        assert "## Account" in result.output


class TestGlobalOptionsE2E:
    """Test global CLI options."""

    def test_version(self, runner):
        """Test version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_help(self, runner):
        """Test help flag."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Tavily CLI" in result.output
        assert "search" in result.output
        assert "extract" in result.output
        assert "crawl" in result.output
        assert "map" in result.output
        assert "usage" in result.output

    def test_verbose_mode(self, runner):
        """Test verbose flag enables debug output."""
        result = runner.invoke(cli, ["-v", "usage"])
        assert result.exit_code == 0
        # Verbose mode should still complete successfully
        assert "API Usage" in result.output
