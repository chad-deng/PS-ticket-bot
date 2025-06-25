# PS-ticket-bot Tests

This directory contains the test suite for the PS-ticket-bot application.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_main.py             # Main application tests
├── test_ai_comments.py      # AI comment generation tests
├── test_jira_integration.py # JIRA integration tests
├── test_jira_operations.py  # JIRA operations API tests
├── test_quality_engine.py   # Quality assessment tests
├── test_queue.py            # Queue and task processing tests
├── test_logging.py          # Logging functionality tests
└── README.md               # This file
```

## Test Categories

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests (default)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.core` - Core functionality tests
- `@pytest.mark.slow` - Slow tests that may take longer
- `@pytest.mark.external` - Tests requiring external services

## Running Tests

### Using the Test Runner Script

```bash
# Run all tests
python scripts/run_tests.py

# Run specific test categories
python scripts/run_tests.py unit
python scripts/run_tests.py integration
python scripts/run_tests.py api

# Run with verbose output
python scripts/run_tests.py --verbose

# Run without coverage
python scripts/run_tests.py --no-coverage

# Clean artifacts before running
python scripts/run_tests.py --clean
```

### Using pytest directly

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_main.py

# Run tests with specific marker
pytest -m unit
pytest -m "not slow"

# Run with coverage
pytest --cov=app --cov-report=html

# Run with verbose output
pytest -v
```

## Test Configuration

Test configuration is managed in:

- `pytest.ini` - Main pytest configuration
- `tests/conftest.py` - Shared fixtures and setup

### Key Configuration Options

- Coverage threshold: 70%
- Test discovery: `test_*.py` files
- Markers: Strict marker enforcement
- Reports: HTML coverage reports in `htmlcov/`

## Shared Fixtures

The `conftest.py` file provides shared fixtures:

- `client` - FastAPI test client
- `sample_ticket` - Standard test ticket
- `high_quality_ticket` - High-quality test ticket
- `low_quality_ticket` - Low-quality test ticket
- `sample_jira_user` - Test JIRA user
- `sample_quality_assessment` - Test quality assessment
- `mock_settings` - Mocked application settings
- `mock_config_manager` - Mocked configuration manager
- `mock_jira_response` - Mocked JIRA API response

## Test Data

Test data is created using fixtures to ensure consistency and reduce duplication. All test tickets include:

- Realistic JIRA ticket structure
- Proper field validation
- Various quality levels
- Different issue types and priorities

## Mocking Strategy

Tests use extensive mocking to:

- Isolate units under test
- Avoid external API calls
- Ensure consistent test environments
- Speed up test execution

Key mocked components:
- JIRA API client
- Gemini AI client
- Configuration manager
- Queue/task system
- Database connections

## Coverage Requirements

- Minimum coverage: 70%
- Focus on core business logic
- API endpoint coverage
- Error handling paths

## Best Practices

1. **Use shared fixtures** - Leverage `conftest.py` fixtures
2. **Mock external dependencies** - Don't make real API calls
3. **Test error conditions** - Include negative test cases
4. **Use descriptive names** - Test names should explain what they test
5. **Keep tests focused** - One concept per test
6. **Use appropriate markers** - Categorize tests properly

## Continuous Integration

Tests are designed to run in CI environments:

- No external dependencies required
- Fast execution (< 2 minutes)
- Comprehensive coverage
- Clear failure reporting

## Troubleshooting

### Common Issues

1. **Import errors** - Ensure all dependencies are installed
2. **Mock failures** - Check mock setup in fixtures
3. **Coverage failures** - Add tests for uncovered code
4. **Slow tests** - Mark with `@pytest.mark.slow`

### Debugging Tests

```bash
# Run with debugging output
pytest -v -s

# Run specific test with debugging
pytest tests/test_main.py::TestMainEndpoints::test_root_endpoint -v -s

# Drop into debugger on failure
pytest --pdb
```

## Maintenance

Regular maintenance tasks:

1. **Update fixtures** - Keep test data current
2. **Review coverage** - Ensure adequate coverage
3. **Clean artifacts** - Use cleanup scripts
4. **Update mocks** - Keep mocks aligned with real APIs
5. **Performance** - Monitor test execution time
