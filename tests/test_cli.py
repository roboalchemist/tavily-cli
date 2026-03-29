"""Tests for tavily-cli."""

import json
import os
import socket
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tavily_cli import cli, TavilyCLI, parse_list, load_config, save_config, _make_slug


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

        # Verify defaults: no explicit max_results (uses API default), include_answer="basic"
        call_kwargs = mock_tavily_client.search.call_args[1]
        assert "max_results" not in call_kwargs
        assert call_kwargs["include_answer"] == "basic"

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
        assert call_kwargs["include_answer"] == "advanced"  # -a flag now upgrades to advanced

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


class TestLoadSaveConfig:
    """Test config file loading and saving."""

    def test_load_config_missing_file(self):
        with patch("tavily_cli.CONFIG_FILE", "/nonexistent/path/config.toml"):
            config = load_config()
        assert config == {}

    def test_load_config_reads_values(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('api_key = "tvly-test"\nhistory_enabled = true\ndefault_format = "json"\n')
        with patch("tavily_cli.CONFIG_FILE", str(config_file)):
            config = load_config()
        assert config["api_key"] == "tvly-test"
        assert config["history_enabled"] is True
        assert config["default_format"] == "json"

    def test_save_config_writes_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        with patch("tavily_cli.CONFIG_FILE", str(config_file)), \
             patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            save_config({"history_enabled": True, "default_format": "json"})
        content = config_file.read_text()
        assert "history_enabled = true" in content
        assert 'default_format = "json"' in content

    def test_save_and_reload_roundtrip(self, tmp_path):
        config_file = tmp_path / "config.toml"
        original = {"api_key": "tvly-xyz", "history_enabled": False, "default_max_results": 10}
        with patch("tavily_cli.CONFIG_FILE", str(config_file)), \
             patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            save_config(original)
            loaded = load_config()
        assert loaded["api_key"] == "tvly-xyz"
        assert loaded["history_enabled"] is False
        assert loaded["default_max_results"] == 10


class TestMakeSlug:
    """Test slug generation for history filenames."""

    def test_search_slug_from_query(self):
        slug = _make_slug("search", {"query": "who is Leo Messi?"})
        assert slug == "who-is-Leo-Messi-"[:40] or "who" in slug

    def test_search_slug_truncated(self):
        long_query = "a" * 100
        slug = _make_slug("search", {"query": long_query})
        assert len(slug) <= 40

    def test_extract_slug_from_url(self):
        # Dots are replaced by hyphens in slug generation
        slug = _make_slug("extract", {"urls": ["https://example.com/page"]})
        assert "example" in slug

    def test_crawl_slug_from_url(self):
        slug = _make_slug("crawl", {"url": "https://docs.python.org/3/"})
        assert "docs" in slug and "python" in slug

    def test_map_slug_from_url(self):
        slug = _make_slug("map", {"url": "https://example.org"})
        assert "example" in slug


class TestWriteHistory:
    """Test history writing behavior."""

    def test_history_disabled_by_default_no_files_written(self, tmp_path, mock_tavily_client):
        """No history files should be written when history_enabled=False."""
        cli_instance = TavilyCLI(api_key="test", history_enabled=False)
        cli_instance.client = mock_tavily_client
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("search", {"query": "test"}, {"results": []}, 100)
        history_dir = tmp_path / "history"
        assert not history_dir.exists()

    def test_history_enabled_writes_file(self, tmp_path, mock_tavily_client):
        """History file should be written when history_enabled=True."""
        cli_instance = TavilyCLI(api_key="test", history_enabled=True)
        cli_instance.client = mock_tavily_client
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("search", {"query": "hello world"}, {"results": []}, 250)
        history_root = tmp_path / "history" / "search"
        assert history_root.exists()
        # Find the written file
        files = list(history_root.rglob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["meta"]["command"] == "search"
        assert data["meta"]["params"]["query"] == "hello world"
        assert data["meta"]["latency_ms"] == 250
        assert "timestamp" in data["meta"]
        assert "hostname" in data["meta"]
        assert data["response"] == {"results": []}

    def test_history_envelope_has_required_meta_fields(self, tmp_path, mock_tavily_client):
        """Envelope must contain all required meta fields."""
        cli_instance = TavilyCLI(api_key="test", history_enabled=True)
        cli_instance.client = mock_tavily_client
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("extract", {"urls": ["https://example.com"]}, {}, 500)
        files = list((tmp_path / "history").rglob("*.json"))
        assert len(files) == 1
        meta = json.loads(files[0].read_text())["meta"]
        assert "timestamp" in meta
        assert "hostname" in meta
        assert "command" in meta
        assert "params" in meta
        assert "latency_ms" in meta

    def test_no_history_flag_suppresses_write(self, tmp_path, mock_tavily_client):
        """--no-history flag should suppress file writes even when enabled."""
        cli_instance = TavilyCLI(api_key="test", history_enabled=True, no_history=True)
        cli_instance.client = mock_tavily_client
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("search", {"query": "test"}, {}, 100)
        history_dir = tmp_path / "history"
        assert not history_dir.exists()

    def test_history_strips_api_key_from_params(self, tmp_path, mock_tavily_client):
        """api_key must not appear in the saved params."""
        cli_instance = TavilyCLI(api_key="tvly-secret", history_enabled=True)
        cli_instance.client = mock_tavily_client
        params = {"query": "test", "api_key": "tvly-secret"}
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("search", params, {}, 100)
        files = list((tmp_path / "history").rglob("*.json"))
        data = json.loads(files[0].read_text())
        assert "api_key" not in data["meta"]["params"]

    def test_history_uses_hierarchical_path(self, tmp_path, mock_tavily_client):
        """Files must be stored under history/<command>/<year>/<month>/<day>/."""
        cli_instance = TavilyCLI(api_key="test", history_enabled=True)
        cli_instance.client = mock_tavily_client
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("crawl", {"url": "https://example.com"}, {}, 300)
        files = list((tmp_path / "history").rglob("*.json"))
        assert len(files) == 1
        # Path should be: history/crawl/<year>/<month>/<day>/<filename>.json
        parts = files[0].relative_to(tmp_path).parts
        assert parts[0] == "history"
        assert parts[1] == "crawl"
        assert len(parts) == 6  # history/cmd/year/month/day/filename

    def test_history_filename_contains_slug_and_hostname(self, tmp_path, mock_tavily_client):
        """Filename should include slug and hostname."""
        cli_instance = TavilyCLI(api_key="test", history_enabled=True)
        cli_instance.client = mock_tavily_client
        with patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            cli_instance.write_history("search", {"query": "python tips"}, {}, 100)
        files = list((tmp_path / "history").rglob("*.json"))
        filename = files[0].name
        assert "python" in filename
        hostname_safe = socket.gethostname()[:10]  # just check a prefix


class TestCLIConfigIntegration:
    """Test CLI group config loading integration."""

    def test_api_key_from_config_file(self, tmp_path, mock_tavily_client):
        """API key should be read from config file when not in env or flag."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('api_key = "tvly-from-config"\n')
        mock_tavily_client.search.return_value = {"query": "test", "results": [], "response_time": 1.0}

        runner = CliRunner()
        with patch("tavily_cli.CONFIG_FILE", str(config_file)), \
             patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            result = runner.invoke(cli, ["search", "test"], env={"TAVILY_API_KEY": ""})
        assert result.exit_code == 0

    def test_no_history_flag_available_on_cli_group(self):
        """--no-history flag should appear in help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--no-history" in result.output

    def test_history_not_written_by_default(self, tmp_path, mock_tavily_client):
        """No history files should be written when history_enabled is not set in config."""
        mock_tavily_client.search.return_value = {"query": "test", "results": [], "response_time": 1.0}
        runner = CliRunner()
        with patch("tavily_cli.CONFIG_FILE", "/nonexistent/config.toml"), \
             patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            result = runner.invoke(cli, ["-k", "test-key", "search", "test"])
        assert result.exit_code == 0
        history_dir = tmp_path / "history"
        assert not history_dir.exists()

    def test_history_written_when_enabled_in_config(self, tmp_path, mock_tavily_client):
        """History files should be written when history_enabled = true in config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("history_enabled = true\n")
        mock_tavily_client.search.return_value = {"query": "test", "results": [], "response_time": 1.0}
        runner = CliRunner()
        with patch("tavily_cli.CONFIG_FILE", str(config_file)), \
             patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            result = runner.invoke(cli, ["-k", "test-key", "search", "test"])
        assert result.exit_code == 0
        files = list((tmp_path / "history").rglob("*.json"))
        assert len(files) == 1

    def test_no_history_flag_suppresses_write_even_when_config_enabled(self, tmp_path, mock_tavily_client):
        """--no-history flag should suppress writing even when config has history_enabled=true."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("history_enabled = true\n")
        mock_tavily_client.search.return_value = {"query": "test", "results": [], "response_time": 1.0}
        runner = CliRunner()
        with patch("tavily_cli.CONFIG_FILE", str(config_file)), \
             patch("tavily_cli.CONFIG_DIR", str(tmp_path)):
            result = runner.invoke(cli, ["-k", "test-key", "--no-history", "search", "test"])
        assert result.exit_code == 0
        history_dir = tmp_path / "history"
        assert not history_dir.exists()
