# AI integration

`.dtsx` packages are dense and hard to read by hand, which makes them a natural
fit for AI-assisted exploration. Two complementary options ship with this
project.

## MCP server

An optional [MCP](https://modelcontextprotocol.io) server exposes the parser as
tools to any MCP-compatible client (Claude Desktop, Claude Code, Cursor, …).

```bash
pip install "pydtsx-parser[mcp]"
```

Then register the `pydtsx-parser-mcp` command with your client:

```json
{
  "mcpServers": {
    "pydtsx-parser": {
      "command": "pydtsx-parser-mcp"
    }
  }
}
```

Tools provided:

| Tool | Purpose |
|---|---|
| `get_package_summary` | High-level overview — best first call |
| `get_sql_code` | Extract embedded SQL statements |
| `get_data_lineage` | Control flow edges plus source → destination tracing |
| `get_data_flows` | Full data flow component detail and column mappings |
| `parse_dtsx_file` | Full structured JSON for one file |
| `parse_ssis_directory` | Full structured JSON for a project |

## Claude Skill

[`skills/pydtsx-parser/SKILL.md`](https://github.com/lamiskin/pydtsx-parser/blob/main/skills/pydtsx-parser/SKILL.md)
is a portable
[Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
that teaches Claude when and how to parse SSIS files with the CLI and how to
interpret the JSON — no running server required. Copy the
`skills/pydtsx-parser/` folder into your `.claude/skills/` directory to use it.

## Which one?

Use the **MCP server** for interactive, on-demand parsing inside a client that
cannot run shell commands. Use the **Skill** for a portable, dependency-light
way to give any shell-capable agent the know-how — it pairs with the CLI and
`jq` and needs no server process.

Either way, give the model the [LLM context guide](LLM_CONTEXT.md) when it
needs to interpret parser output in depth.
