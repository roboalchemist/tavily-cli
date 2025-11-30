"""Tests for tavily-cli."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tavily_cli import cli, TavilyCLI, parse_list


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_tavily_client():
    """Create a mock TavilyClient."""
    with patch("tavily_cli.TavilyClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


class TestParseList:
    """Tests for the parse_list helper function."""

    def test_parse_list_with_values(self):
        result = parse_list(None, None, "a,b,c")
        assert result == ["a", "b", "c"]

    def test_parse_list_with_spaces(self):
        result = parse_list(None, None, "a, b , c")
        assert result == ["a", "b", "c"]

    def test_parse_list_empty(self):
        result = parse_list(None, None, "")
        assert result is None

    def test_parse_list_none(self):
        result = parse_list(None, None, None)
        assert result is None


class TestCLIHelp:
    """Test CLI help output."""

    def test_main_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Tavily CLI" in result.output
        assert "search" in result.output
        assert "extract" in result.output
        assert "crawl" in result.output
        assert "map" in result.output
        assert "usage" in result.output

    def test_search_help(self, runner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "Execute a web search query" in result.output
        assert "--depth" in result.output
        assert "--topic" in result.output

    def test_extract_help(self, runner):
        result = runner.invoke(cli, ["extract", "--help"])
        assert result.exit_code == 0
        assert "Extract content" in result.output

    def test_crawl_help(self, runner):
        result = runner.invoke(cli, ["crawl", "--help"])
        assert result.exit_code == 0
        assert "Crawl a website" in result.output

    def test_map_help(self, runner):
        result = runner.invoke(cli, ["map", "--help"])
        assert result.exit_code == 0
        assert "Generate a site map" in result.output

    def test_usage_help(self, runner):
        result = runner.invoke(cli, ["usage", "--help"])
        assert result.exit_code == 0
        assert "usage statistics" in result.output


class TestCLINoApiKey:
    """Test CLI behavior without API key."""

    def test_no_api_key_error(self, runner):
        result = runner.invoke(cli, ["search", "test"], env={"TAVILY_API_KEY": ""})
        assert result.exit_code == 1
        assert "No API key provided" in result.output


class TestSearch:
    """Test search command."""

    def test_search_basic(self, runner, mock_tavily_client):
        mock_tavily_client.search.return_value = {
            "query": "test query",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content",
                    "score": 0.9,
                }
            ],
            "response_time": 1.5,
        }

        result = runner.invoke(cli, ["-k", "test-key", "search", "test query"])
        assert result.exit_code == 0
        assert "Test Result" in result.output
        mock_tavily_client.search.assert_called_once()

    def test_search_with_options(self, runner, mock_tavily_client):
        mock_tavily_client.search.return_value = {
            "query": "test",
            "results": [],
            "answer": "Test answer",
            "response_time": 1.0,
        }

        result = runner.invoke(
            cli,
            ["-k", "test-key", "search", "test", "-d", "advanced", "-t", "news", "-n", "10", "-a"],
        )
        assert result.exit_code == 0

        call_kwargs = mock_tavily_client.search.call_args[1]
        assert call_kwargs["search_depth"] == "advanced"
        assert call_kwargs["topic"] == "news"
        assert call_kwargs["max_results"] == 10
        assert call_kwargs["include_answer"] == "basic"

    def test_search_json_output(self, runner, mock_tavily_client):
        mock_tavily_client.search.return_value = {
            "query": "test",
            "results": [],
            "response_time": 1.0,
        }

        result = runner.invoke(cli, ["-k", "test-key", "-f", "json", "search", "test"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["query"] == "test"


class TestExtract:
    """Test extract command."""

    def test_extract_single_url(self, runner, mock_tavily_client):
        mock_tavily_client.extract.return_value = {
            "results": [
                {
                    "url": "https://example.com",
                    "raw_content": "Page content here",
                }
            ],
            "failed_results": [],
            "response_time": 0.5,
        }

        result = runner.invoke(cli, ["-k", "test-key", "extract", "https://example.com"])
        assert result.exit_code == 0
        assert "example.com" in result.output

    def test_extract_multiple_urls(self, runner, mock_tavily_client):
        mock_tavily_client.extract.return_value = {
            "results": [],
            "failed_results": [],
            "response_time": 0.5,
        }

        result = runner.invoke(
            cli,
            ["-k", "test-key", "extract", "https://example.com", "https://example.org"],
        )
        assert result.exit_code == 0

        call_kwargs = mock_tavily_client.extract.call_args[1]
        assert len(call_kwargs["urls"]) == 2


class TestCrawl:
    """Test crawl command."""

    def test_crawl_basic(self, runner, mock_tavily_client):
        mock_tavily_client.crawl.return_value = {
            "base_url": "https://example.com",
            "results": [
                {
                    "url": "https://example.com/page1",
                    "raw_content": "Content 1",
                }
            ],
            "response_time": 5.0,
        }

        result = runner.invoke(cli, ["-k", "test-key", "crawl", "https://example.com"])
        assert result.exit_code == 0
        assert "example.com" in result.output

    def test_crawl_with_instructions(self, runner, mock_tavily_client):
        mock_tavily_client.crawl.return_value = {
            "base_url": "https://example.com",
            "results": [],
            "response_time": 5.0,
        }

        result = runner.invoke(
            cli,
            ["-k", "test-key", "crawl", "https://example.com", "-i", "Find API docs"],
        )
        assert result.exit_code == 0

        call_kwargs = mock_tavily_client.crawl.call_args[1]
        assert call_kwargs["instructions"] == "Find API docs"


class TestMap:
    """Test map command."""

    def test_map_basic(self, runner, mock_tavily_client):
        mock_tavily_client.map.return_value = {
            "base_url": "https://example.com",
            "results": [
                "https://example.com/page1",
                "https://example.com/page2",
            ],
            "response_time": 2.0,
        }

        result = runner.invoke(cli, ["-k", "test-key", "map", "https://example.com"])
        assert result.exit_code == 0
        assert "page1" in result.output
        assert "page2" in result.output


class TestUsage:
    """Test usage command."""

    def test_usage(self, runner, mock_tavily_client):
        with patch("tavily_cli.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "key": {
                    "usage": 150,
                    "limit": 1000,
                },
                "account": {
                    "current_plan": "Researcher",
                    "plan_usage": 500,
                    "plan_limit": 1000,
                    "paygo_usage": 0,
                    "paygo_limit": 100,
                },
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = runner.invoke(cli, ["-k", "test-key", "usage"])
            assert result.exit_code == 0
            assert "150" in result.output
            assert "Researcher" in result.output


class TestTavilyCLI:
    """Test TavilyCLI class methods."""

    def test_display_search_results_text(self, mock_tavily_client, capsys):
        cli_instance = TavilyCLI(api_key="test", output_format="text")
        cli_instance.client = mock_tavily_client

        response = {
            "query": "test",
            "results": [
                {
                    "title": "Test",
                    "url": "https://example.com",
                    "content": "Content",
                    "score": 0.9,
                }
            ],
            "response_time": 1.0,
        }

        cli_instance.display_search_results(response)
        captured = capsys.readouterr()
        assert "Test" in captured.out

    def test_display_search_results_json(self, mock_tavily_client, capsys):
        cli_instance = TavilyCLI(api_key="test", output_format="json")
        cli_instance.client = mock_tavily_client

        response = {
            "query": "test",
            "results": [],
        }

        cli_instance.display_search_results(response)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["query"] == "test"

    def test_display_usage_text(self, mock_tavily_client, capsys):
        cli_instance = TavilyCLI(api_key="test", output_format="text")
        cli_instance.client = mock_tavily_client

        response = {
            "key": {"usage": 100, "limit": 1000},
            "account": {
                "current_plan": "Test",
                "plan_usage": 100,
                "plan_limit": 1000,
                "paygo_usage": 0,
                "paygo_limit": 0,
            },
        }

        cli_instance.display_usage(response)
        captured = capsys.readouterr()
        assert "100" in captured.out
        assert "Test" in captured.out
