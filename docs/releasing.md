# Releasing to PyPI

Releases are published by GitHub Actions through PyPI trusted publishing. No PyPI token is stored in the repository or in GitHub secrets; PyPI trusts the workflow's identity instead.

## One-time setup

1. **Register the publisher on PyPI.** Sign in at https://pypi.org, open *Your projects*, then *Publishing*, and under *Add a new pending publisher* fill in:

   | Field | Value |
   |---|---|
   | PyPI project name | `llmwarden` |
   | Owner | `nadeem4` |
   | Repository name | `llmwarden` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   A pending publisher reserves the name; the project is created on the first publish.

2. **Create the GitHub environment.** In the repository, *Settings*, *Environments*, *New environment*, name it `pypi`. Optionally add yourself as a required reviewer so a tag push waits for your approval before publishing.

3. **Optional, recommended: test on TestPyPI first.** Repeat step 1 at https://test.pypi.org with environment name `testpypi`, and add a second job to the workflow pointing `pypa/gh-action-pypi-publish` at `repository-url: https://test.pypi.org/legacy/`. Not set up by default to keep the workflow small.

## Each release

1. Update `CHANGELOG.md`: rename the unreleased section to the version and date.
2. Set the version in `pyproject.toml`, for example with `uv version 0.1.0`.
3. Commit: `git commit -am "chore: release 0.1.0"`.
4. Tag and push: `git tag v0.1.0 && git push && git push --tags`.

The `publish` workflow then runs lint, types and tests, checks that the tag matches the version in `pyproject.toml`, builds the wheel and sdist with `uv build`, and uploads them. The release appears at https://pypi.org/project/llmwarden/ within a minute or two.

## Local check before tagging

```
uv build
uv run --isolated --no-project --with dist/llmwarden-*.whl python -c "import llmwarden; print(llmwarden.__version__)"
```

## What is published

The wheel contains `src/llmwarden` only. Tests, docs and examples ship in the sdist for reference but are not installed. Extras (`openai`, `anthropic`, `litellm`, `aws`, `azure`, `gcp`, `vault`, `otel`, `dotenv`, `all`) come from `pyproject.toml`.
