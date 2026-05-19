# Skills

This folder contains reusable scripts that opencode can discover and execute on demand.

## Usage

Ask opencode to run a skill:

- "Run the data_analysis skill on the CSV in my session folder"
- "Execute fetch_github_repos.py and save the output"
- "List available skills and run the most relevant one"

## Conventions

- One script per skill, named descriptively: `fetch_linkedin_posts.py`, `generate_report.py`
- Each script should be self-contained and accept arguments via `sys.argv` or environment variables
- Output results to stdout or write files to the session working directory

## Available Skills

Add your `.py` or `.sh` scripts here.
