"""Setup script for NightShift"""

from setuptools import setup, find_packages

setup(
    name="nightshift",
    version="0.1.0",
    description="Automated Research Assistant System powered by Claude Code",
    author="James Alvey",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "rich>=13.0.0",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
        "slack-sdk>=3.23.0",
        "flask>=3.0.0",
        "flask-limiter>=3.5.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nightshift=nightshift.interfaces.cli:main",
        ],
    },
    python_requires=">=3.8",
)
