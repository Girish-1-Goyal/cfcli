# CFCLI - Codeforces Command Line Interface

A Python-based terminal application that automates Codeforces contest workflows to streamline your competitive programming experience.

## Features

- **Authentication**: Securely store and use your Codeforces credentials
- **Contest Management**: Fetch upcoming, running, and past contests
- **Problem Setup**: Generate C++ source files from templates with proper headers
- **Submission**: Submit your solution directly from the command line
- **Verdict Tracking**: Monitor submission verdicts in real-time

## Installation

### Prerequisites

- Python 3.6+
- pip (Python package manager)

### Install from Source

1. Clone this repository or download the source code
2. Install required dependencies:

```bash
pip install click colorama python-dotenv requests
```

3. Make the script executable:

```bash
chmod +x cfcli.py
```

4. (Optional) Create a symbolic link to use the tool from anywhere:

```bash
sudo ln -s $(pwd)/cfcli.py /usr/local/bin/cfcli
```

## Configuration

### Environment Variables

You can set your Codeforces credentials using environment variables to avoid entering them each time:

1. Create a `.env` file in the same directory as the script:

```
CF_HANDLE=your_handle
CF_API_KEY=your_api_key
CF_API_SECRET=your_secret_key
```

2. Ensure the `.env` file is included in your `.gitignore` to prevent accidentally sharing your credentials.

### API Keys

To obtain your Codeforces API key and secret:

1. Log into your Codeforces account
2. Go to your profile settings
3. Navigate to the API section
4. Generate a new API key and secret

## Usage

### Authentication

Login to Codeforces with your credentials:

```bash
cfcli login
```

This command will prompt you for your Codeforces handle, API key, and secret if they're not already set in environment variables.

### Fetching Contests

View upcoming, running, or past contests:

```bash
# View upcoming contests (default)
cfcli fetch

# View running contests
cfcli fetch running

# View past contests
cfcli fetch past

# Limit the number of contests shown
cfcli fetch past --limit 10
```

### Generating Problem Files

Create C++ source files for contest problems:

```bash
# Generate a file for a specific problem
cfcli generate 1842 A

# Generate files for all problems in a contest
cfcli generate 1842 --all

# Use a custom template directory
cfcli generate 1842 --all --template-dir ~/cpp_templates
```

The first time you run this command, a default template will be created in `~/.cfcli/templates/template.cpp`. You can customize this template to suit your preferences.

### Submitting Solutions

Submit your solution to Codeforces:

```bash
# Submit a solution
cfcli submit Contest1842_A.cpp
```

### Checking Submission Status

Check the verdict of your submission:

```bash
# Check status of a specific submission
cfcli status 123456789

# Check all submissions for a specific contest
cfcli status --contest-id 1842
```

## Templates

The default template directory is located at `~/.cfcli/templates`. You can create a `template.cpp` file here to use as your default template for problem solving. Alternatively, specify a custom template directory when generating problem files.

## Troubleshooting

### Authentication Issues

- Ensure your API key and secret are correct
- Check that your Codeforces handle exists and is spelled correctly
- If you've recently changed your password, you may need to generate a new API key

### Submission Problems

- Ensure you're logged in (`cfcli login`)
- Check that the file exists and has the correct naming format
- Verify that you have an active internet connection
- Make sure the contest is still running and accepting submissions

### API Rate Limiting

- The tool implements caching to minimize API calls
- If you receive rate limiting errors, wait a few minutes before trying again

## License

MIT License

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests. 