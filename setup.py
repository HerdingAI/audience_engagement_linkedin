"""Setup configuration for LinkedIn-Engagement package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read requirements
def read_requirements(filename):
    """Read requirements from file."""
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="linkedin-engagement",
    version="1.0.0",
    author="Data-Carlos",
    author_email="",
    description="A Python-based automation suite for LinkedIn engagement",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Data-Carlos/LinkedIn-engagement",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.10",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("requirements-dev.txt"),
    },
    entry_points={
        "console_scripts": [
            "linkedin-commenter=linkedin_commenter:main",
            "linkedin-post-liker=linkedin_post_liker:main",
            "linkedin-comment-poster=linkedin_comment_poster:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml"],
    },
    project_urls={
        "Bug Reports": "https://github.com/Data-Carlos/LinkedIn-engagement/issues",
        "Source": "https://github.com/Data-Carlos/LinkedIn-engagement",
        "Documentation": "https://github.com/Data-Carlos/LinkedIn-engagement#readme",
    },
)
