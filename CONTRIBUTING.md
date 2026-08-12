# Contributing to Aether

Thank you for your interest in contributing to **Aether**! We welcome bug fixes, documentation improvements, feature proposals, and pull requests from developers of all backgrounds.

---

## 📜 Development Guidelines & Code Standards

### Prerequisites
* **Python 3.11** or higher
* **Poetry** for dependency management
* **Docker & Docker Compose** for local databases

### Local Environment Setup

1. **Fork and Clone the Repository:**
   ```bash
   git clone https://github.com/rhythem27/aether.git
   cd aether
   ```

2. **Install Dependencies:**
   ```bash
   poetry install
   ```

3. **Install Pre-Commit Hooks:**
   ```bash
   poetry run pre-commit install
   ```

4. **Spin Up Infrastructure:**
   ```bash
   docker compose up -d
   ```

---

## 🎨 Code Style & Quality Requirements

Before submitting code, ensure it passes all static checks and unit tests:

1. **Ruff Linter:**
   ```bash
   poetry run ruff check .
   ```

2. **Black Formatting:**
   ```bash
   poetry run black --check .
   ```

3. **MyPy Type Checking:**
   ```bash
   poetry run mypy backend
   ```

4. **Pytest Test Suite:**
   ```bash
   poetry run pytest
   ```

---

## 🌿 Git Workflow & Branch Conventions

* **Branch Naming:**
  * Feature branches: `feat/short-description`
  * Bug fixes: `fix/short-description`
  * Documentation: `docs/short-description`
* **Commit Messages:** Follow Conventional Commits format (e.g. `feat(agent): add valuation risk checker`, `fix(rag): resolve qdrant score calculation`).

---

## 🚀 Submitting a Pull Request (PR)

1. Ensure all unit tests pass locally.
2. Push your feature branch to your fork.
3. Open a Pull Request targeting the `main` branch.
4. Fill out the [Pull Request Template] completely.
5. A maintainer will review your PR and provide feedback.

Thank you for helping build a world-class financial intelligence platform!
