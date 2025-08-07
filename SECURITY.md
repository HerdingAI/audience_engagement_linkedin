# Security Policy

## Supported Versions

We take security seriously and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in LinkedIn-Engagement, please report it responsibly:

### How to Report

1. **Do not** create a public GitHub issue for security vulnerabilities
2. Email us at: [create a security email] or use GitHub's private vulnerability reporting
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **Investigation**: We will investigate and validate the vulnerability
- **Timeline**: We aim to provide an initial response within 7 days
- **Resolution**: Critical vulnerabilities will be patched within 30 days
- **Credit**: We will credit you in our security advisory (unless you prefer to remain anonymous)

## Security Best Practices

When using LinkedIn-Engagement:

### API Keys and Credentials
- Never commit API keys or credentials to version control
- Use environment variables (.env file) for sensitive data
- Rotate API keys regularly
- Use read-only API keys when possible

### Database Security
- Keep your SQLite database files secure
- Regularly backup your data
- Don't share database files containing personal information

### Network Security
- Use HTTPS for all API communications
- Consider using VPN when running automation scripts
- Be aware of rate limiting to avoid triggering security measures

### LinkedIn Terms of Service
- Ensure your usage complies with LinkedIn's Terms of Service
- Respect rate limits and user privacy
- Use the tool responsibly and ethically

## Dependencies

We regularly monitor our dependencies for security vulnerabilities:

- Dependencies are tracked in `requirements.txt` and `pyproject.toml`
- We use automated tools to check for known vulnerabilities
- Security updates are applied promptly

## Security Features

LinkedIn-Engagement includes several security features:

- Environment variable based configuration
- No hardcoded credentials
- Secure API communication
- Rate limiting to prevent abuse
- Logging for audit trails

## Scope

This security policy applies to:

- The main LinkedIn-Engagement repository
- All code in the `backend/` directory
- Main automation scripts
- Documentation and configuration files

## Contact

For security-related questions or concerns, please contact the maintainers through:

- GitHub Issues (for general security questions, not vulnerabilities)
- GitHub Security Advisories (for vulnerability reports)

Thank you for helping keep LinkedIn-Engagement and our community safe!
