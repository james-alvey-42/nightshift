# Sample NightShift Tasks

Example tasks to submit for testing the NightShift system.

## Research Tasks

### Academic Paper Search
```bash
nightshift submit "Find recent papers on transformer architecture improvements from 2024 and summarize the key innovations"
```

### Literature Review
```bash
nightshift submit "Search arXiv for papers about diffusion models in the last 6 months and create a summary table with titles, authors, and key contributions"
```

### Technology Survey
```bash
nightshift submit "Research the current state of Rust async runtimes and compare tokio vs async-std with pros/cons"
```

## Data Processing

### CSV Analysis
```bash
nightshift submit "Analyze the sales_data.csv file and generate a report showing top products, monthly trends, and revenue statistics"
```

### JSON Transformation
```bash
nightshift submit "Convert all JSON files in the data/ directory to CSV format with proper header inference"
```

### Log Processing
```bash
nightshift submit "Parse the application logs and extract all ERROR entries from the last week, categorize by error type"
```

## File Operations

### Directory Organization
```bash
nightshift submit "Organize the downloads folder by file type, creating subdirectories for documents, images, videos, and archives"
```

### Duplicate Detection
```bash
nightshift submit "Find duplicate files in the ~/Documents directory using hash comparison and create a report"
```

### Batch Renaming
```bash
nightshift submit "Rename all files in photos/ to format YYYY-MM-DD_NNN.jpg based on EXIF creation date"
```

## Code Generation

### Script Creation
```bash
nightshift submit "Create a Python script that monitors a directory for new files and automatically backs them up to S3"
```

### Test Generation
```bash
nightshift submit "Generate unit tests for the UserService class with 80%+ coverage"
```

### Documentation
```bash
nightshift submit "Generate API documentation from the FastAPI endpoints in app/routes/ with example requests/responses"
```

## Analysis Tasks

### Code Review
```bash
nightshift submit "Review the authentication module for security vulnerabilities and common issues"
```

### Performance Analysis
```bash
nightshift submit "Profile the data processing pipeline and identify bottlenecks, suggest optimizations"
```

### Dependency Audit
```bash
nightshift submit "Check all Python dependencies for known security vulnerabilities and outdated versions"
```

## Content Creation

### Report Generation
```bash
nightshift submit "Create a quarterly progress report based on the commit history and issue tracker data"
```

### Email Draft
```bash
nightshift submit "Draft a professional email to the team announcing the new deployment process with migration timeline"
```

### README Update
```bash
nightshift submit "Update the README.md with installation instructions for Windows, macOS, and Linux"
```

## Integration Tasks

### API Testing
```bash
nightshift submit "Test all REST API endpoints in the OpenAPI spec and verify response schemas match documentation"
```

### Database Migration
```bash
nightshift submit "Create an Alembic migration to add email verification fields to the users table"
```

### CI/CD Setup
```bash
nightshift submit "Add GitHub Actions workflow for running tests, linting, and deploying to staging on PR merge"
```

## Simple Test Cases

### Quick Math
```bash
nightshift submit "Calculate the compound interest on $10,000 at 5% annual rate for 10 years"
```

### File Check
```bash
nightshift submit "Check if requirements.txt exists and list all dependencies with their versions"
```

### Git Status
```bash
nightshift submit "Show git status and list files modified in the last commit"
```

## Complex Multi-Step

### Full Pipeline
```bash
nightshift submit "Download the latest dataset from kaggle.com/dataset/xyz, clean the data, perform exploratory analysis, train a simple model, and generate a report with visualizations"
```

### Release Preparation
```bash
nightshift submit "Prepare for v1.0.0 release: update version numbers, generate changelog from commits, run full test suite, create release notes, and tag the commit"
```

### Codebase Refactoring
```bash
nightshift submit "Refactor the legacy payment processing module to use the new PaymentService interface, update tests, and verify backwards compatibility"
```
