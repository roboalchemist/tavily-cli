.PHONY: install install-dev test test-unit test-e2e lint clean help

help:
	@echo "Available targets:"
	@echo "  install      Install tavily-cli"
	@echo "  install-dev  Install with development dependencies"
	@echo "  test         Run all tests (unit + e2e)"
	@echo "  test-unit    Run unit tests only (no API calls)"
	@echo "  test-e2e     Run end-to-end tests (requires TAVILY_API_KEY)"
	@echo "  lint         Run linter"
	@echo "  clean        Clean build artifacts"

install:
	pip install -r requirements.txt
	chmod +x tavily_cli.py
	@echo ""
	@echo "Installation complete!"
	@echo "Add this directory to your PATH or create a symlink:"
	@echo "  ln -sf $(PWD)/tavily_cli.py /usr/local/bin/tavily"
	@echo ""
	@echo "Or install as a package:"
	@echo "  pip install -e ."

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

test-unit:
	pytest tests/test_cli.py -v

test-e2e:
	pytest tests/test_e2e.py -v

lint:
	ruff check tavily_cli.py
	ruff format --check tavily_cli.py

format:
	ruff format tavily_cli.py

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info
	rm -rf dist
	rm -rf build
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -delete
