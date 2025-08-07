# Contributing to LinkedIn-Engagement

Thank you for your interest in contributing to LinkedIn-Engagement! We welcome contributions from the community and are pleased to have you here.

## Code of Conduct

By participating in this project, you are expected to uphold our Code of Conduct. Please be respectful and constructive in all interactions.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed after following the steps**
- **Explain which behavior you expected to see instead and why**
- **Include screenshots if applicable**
- **Include your environment details** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

- **Use a clear and descriptive title**
- **Provide a step-by-step description of the suggested enhancement**
- **Provide specific examples to demonstrate the steps**
- **Describe the current behavior and explain which behavior you expected to see instead**
- **Explain why this enhancement would be useful**

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** in your forked repository
3. **Add tests** for any new functionality
4. **Ensure the test suite passes** by running `python -m pytest`
5. **Make sure your code follows the existing style**
6. **Update documentation** if necessary
7. **Create a pull request** with a clear title and description

### Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-username/LinkedIn-engagement.git
   cd LinkedIn-engagement
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create your `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Run tests to ensure everything is working:
   ```bash
   python -m pytest tests/
   ```

### Coding Standards

- **Follow PEP 8** for Python code style
- **Use meaningful variable and function names**
- **Add docstrings** to all functions and classes
- **Keep functions small and focused**
- **Add type hints** where appropriate
- **Write tests** for new functionality

### Testing

- All new features should include tests
- Run the full test suite before submitting: `python -m pytest`
- Ensure all tests pass and maintain good coverage
- Test files should be placed in the `tests/` directory

### Documentation

- Update the README.md if you change functionality
- Add docstrings to new functions and classes
- Update any relevant documentation files
- Include examples for new features

### Commit Messages

- Use clear and meaningful commit messages
- Start with a brief summary (50 chars or less)
- Reference issue numbers when applicable
- Example: `Fix rate limiting bug in comment poster (#123)`

## Project Structure

Understanding the project structure will help you contribute effectively:

```text
linkedin-engagement/
├── backend/                    # Core business logic
│   ├── invitations/           # Invitation management
│   └── linkedin/              # LinkedIn-specific operations
├── scripts/                   # Main automation scripts
├── tests/                     # Test files
├── .env.example              # Environment template
├── requirements.txt          # Dependencies
└── README.md                 # Project documentation
```

## Questions?

If you have questions about contributing, please:

1. Check the existing issues and documentation
2. Create an issue with the "question" label
3. Be specific about what you're trying to accomplish

Thank you for contributing to LinkedIn-Engagement!
