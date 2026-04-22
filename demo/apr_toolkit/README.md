# APR Toolkit for `openai-agents`

Compact, Ubuntu-friendly tools for Automated Program Repair agents using `openai-agents>=0.14`.

## Included tools

- `get_workspace_info`
- `list_files`
- `read_file`
- `search_files`
- `write_file`
- `replace_in_file`
- `replace_lines`
- `execute_command`
- `run_test_target`
- `git_status_summary`
- `git_diff_summary`
- `apply_unified_diff`

## Profiles

- `minimal`: read/search/replace/execute
- `core`: better default for APR loops
- `full`: includes git and patch helpers

## Usage

```python
from agents import Agent, Runner
from apr_toolkit import APRToolContext, build_apr_tools

agent = Agent[APRToolContext](
    name="APR Agent",
    model="gpt-5.4",
    instructions=(
        "You are an automated program repair agent. "
        "Prefer list_files/search_files before broad reads. "
        "Read the smallest relevant span. "
        "Use replace_lines or replace_in_file for surgical edits. "
        "Run focused tests after each change."
    ),
    tools=build_apr_tools("core"),
)

ctx = APRToolContext(root_dir="/path/to/repo")
result = Runner.run_sync(agent, "Fix the failing tests.", context=ctx)
print(result.final_output)
```

## Notes

- All paths are confined to `root_dir`.
- Command execution uses `bash -lc`.
- Outputs are truncated to save tokens.
- `run_test_target` auto-detects a common test command when possible.
- `apply_unified_diff` uses the system `patch` utility if available.
