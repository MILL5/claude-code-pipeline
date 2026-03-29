# Python Test Patterns

## pytest Framework Patterns

Write comprehensive pytest suites following these conventions:

### Test Structure
- Test files named `test_<module>.py` in a `tests/` directory (or alongside source files)
- Test functions named `test_<feature>_<scenario>_<expected_outcome>()`
- Test classes named `Test<Feature>` (no `__init__` method) for grouping related tests
- Use `conftest.py` for shared fixtures at each directory level
- Group related tests with classes or separate files, not just comments

### pytest Fixtures
- Define fixtures in `conftest.py` for cross-file sharing
- Use appropriate scope: `function` (default), `class`, `module`, `session`
- Use `autouse=True` sparingly — only for truly universal setup (like resetting a singleton)
- Fixtures should yield for setup/teardown patterns:
  ```python
  @pytest.fixture
  def db_session():
      session = create_session()
      yield session
      session.rollback()
      session.close()
  ```
- Compose fixtures: fixtures can request other fixtures as parameters
- Use `tmp_path` (built-in) for temporary file/directory needs
- Use `monkeypatch` for environment variables and attribute patching

### Parametrize
- Use `@pytest.mark.parametrize` for testing multiple inputs/outputs:
  ```python
  @pytest.mark.parametrize("input,expected", [
      ("hello", "HELLO"),
      ("world", "WORLD"),
      ("", ""),
  ])
  def test_uppercase(input, expected):
      assert to_upper(input) == expected
  ```
- Give test IDs for clarity: `pytest.param(value, id="descriptive-name")`
- Combine multiple parametrize decorators for cartesian product testing
- Use `pytest.param(..., marks=pytest.mark.xfail)` for expected failures

### Mocking
- **`monkeypatch`** (built-in): For patching attributes, environment variables, dict items
  ```python
  def test_config(monkeypatch):
      monkeypatch.setenv("API_KEY", "test-key")
      monkeypatch.setattr(module, "TIMEOUT", 5)
  ```
- **`unittest.mock.patch`**: For replacing objects in specific module namespaces
  ```python
  @patch("myapp.services.external_api.fetch")
  def test_service(mock_fetch):
      mock_fetch.return_value = {"status": "ok"}
  ```
- **`pytest-mock`** (`mocker` fixture): Cleaner interface for unittest.mock
  ```python
  def test_service(mocker):
      mock_fetch = mocker.patch("myapp.services.fetch")
      mock_fetch.return_value = {"status": "ok"}
  ```
- Prefer dependency injection over mocking when possible
- Use `MagicMock(spec=RealClass)` to catch attribute errors in mocks
- Use `call_args` and `call_args_list` to verify call parameters

### Async Testing
- Install `pytest-asyncio` and mark async tests:
  ```python
  @pytest.mark.asyncio
  async def test_async_fetch():
      result = await fetch_data()
      assert result.status == 200
  ```
- Use `asyncio` mode in `pyproject.toml`: `asyncio_mode = "auto"` or `"strict"`
- Mock async functions with `AsyncMock`:
  ```python
  mock_fetch = AsyncMock(return_value={"data": []})
  ```
- Use `pytest-httpx` for mocking httpx async requests

### Coverage Configuration
- Configure in `pyproject.toml`:
  ```toml
  [tool.coverage.run]
  source = ["src"]
  omit = ["*/tests/*", "*/migrations/*"]

  [tool.coverage.report]
  show_missing = true
  fail_under = 80
  ```
- Use `--cov` flag with pytest-cov: `pytest --cov=mypackage --cov-report=term-missing`
- Focus coverage on business logic; exclude migrations, config, and generated code
- Use `# pragma: no cover` sparingly for genuinely untestable code (platform checks, debug blocks)

### Marker System
- Define custom markers in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "slow: marks tests as slow (deselect with '-m \"not slow\"')",
      "integration: marks integration tests requiring external services",
      "e2e: end-to-end tests",
  ]
  ```
- Use `@pytest.mark.skip(reason="...")` and `@pytest.mark.skipif(condition, reason="...")`
- Use `@pytest.mark.xfail(reason="...")` for known failures
- Run specific markers: `pytest -m "not slow and not integration"`

## Anti-Patterns to Avoid
- Don't use `unittest.TestCase` in pytest projects — use plain functions and fixtures
- Don't share mutable state between tests — each test must be independent
- Don't mock what you don't own — wrap third-party APIs in your own interface, mock that
- Don't write tests that pass when the code is broken (test the assertion itself)
- Don't use `time.sleep()` in tests — use `pytest-timeout` and proper async patterns
- Don't test implementation details — test behavior and contracts
