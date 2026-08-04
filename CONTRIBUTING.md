# Contributing to VM Monitor

First off, thank you for considering contributing to VM Monitor! It's people like you that make VM Monitor such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include logs and error messages**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and explain which behavior you expected to see instead**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Do not include issue numbers in the PR title
* Follow the Python/JavaScript style guides
* Include thoughtfully-worded, well-structured tests
* Document new code
* End all files with a newline

## Development Setup

### Prerequisites

* Docker or Podman
* Python 3.11+
* PostgreSQL 13+
* Node.js 16+ (for frontend development)

### Local Setup

1. Fork and clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/vm-monitor.git
cd vm-monitor
```

2. Create your .env file
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start development environment
```bash
cd docker
podman-compose up -d
```

4. Run backend locally (for development)
```bash
cd docker/backend
pip install -r requirements.txt
uvicorn postgres_backend:app --reload
```

### Running Tests

```bash
# Backend tests
pytest tests/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=. tests/
```

### Code Style

**Python**:
* Follow PEP 8
* Use type hints
* Maximum line length: 100 characters
* Use `black` for formatting
* Use `flake8` for linting

```bash
black .
flake8 .
```

**JavaScript**:
* Use ES6+ syntax
* Semicolons required
* 2 spaces for indentation
* Use `prettier` for formatting

```bash
prettier --write frontend/
```

### Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

Example:
```
Add CVE vulnerability dashboard widget

- Fetch CVE data from backend API
- Display severity badges
- Add filtering by severity level

Fixes #123
```

## Project Structure

```
vm-monitor/
├── docker/              # Container definitions
│   ├── backend/        # FastAPI application
│   ├── telegraf-processor/
│   ├── cve-downloader/
│   └── fact-collector/
├── frontend/           # React dashboard
├── nginx/              # Nginx configuration
├── scripts/            # Deployment scripts
├── tests/              # Test files
└── docs/               # Documentation
```

## Adding New Features

1. Create a new branch
```bash
git checkout -b feature/amazing-feature
```

2. Make your changes

3. Add tests for your changes

4. Ensure all tests pass

5. Commit your changes

6. Push to your fork

7. Open a Pull Request

## Documentation

* Update README.md if needed
* Update ARCHITECTURE.md for architectural changes
* Add docstrings to all functions/classes
* Update API.md for new endpoints

## Questions?

Feel free to open an issue with your question or reach out via GitHub Discussions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
