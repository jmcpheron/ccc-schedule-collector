# Contributing to Rio Hondo College Schedule Collector

Thank you for your interest in contributing! This project welcomes contributions from everyone.

## Ways to Contribute

### 1. Report Issues
- Check if the issue already exists
- Include steps to reproduce
- Provide error messages and logs
- Specify your environment (OS, Python version)

### 2. Improve Documentation
- Fix typos or clarify instructions
- Add examples or use cases
- Translate documentation

### 3. Enhance Code
- Fix bugs
- Add new features
- Improve performance
- Add tests

## Development Setup

1. Fork and clone the repository
2. Run the setup script:
   ```bash
   ./setup.sh
   ```
3. Make your changes
4. Run tests:
   ```bash
   uv run test_collector.py
   ```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small

## Testing

- Write tests for new features
- Ensure existing tests pass
- Test edge cases and error conditions
- Use meaningful test names

## Pull Request Process

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

4. Open a Pull Request with:
   - Clear title and description
   - Link to related issues
   - Screenshots if applicable
   - Test results

## Parser Contributions

When modifying the HTML parser:
- Test with real Rio Hondo HTML files
- Handle edge cases (missing data, malformed HTML)
- Maintain backwards compatibility
- Document any assumptions

## Adding New CLI Commands

New CLI commands should:
- Follow the existing pattern in `cli.py`
- Include help text
- Have proper error handling
- Be documented in the README

## Questions?

Feel free to open an issue for any questions about contributing!