# Society

A terminal-native multi-agent system where persistent AI personas collaborate, debate, specialize, and evolve over time.

## Quick Start

```bash
# Install
pip install -e .

# Set your API key (see Authentication below)
export ANTHROPIC_API_KEY=your-key-here

# Run
society
```

## Authentication

Society uses the Anthropic Python SDK, which supports two authentication methods:

### Option 1: API Key (standard)

Get an API key from [console.anthropic.com](https://console.anthropic.com/) and set it as an environment variable:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
society
```

### Option 2: Claude OAuth Token (for Claude Code users)

If you have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed, you can authenticate using its OAuth token instead of a separate API key. This uses your existing Claude subscription.

```bash
# Print the token (requires Claude Code to be installed and authenticated)
claude auth print-oauth-token

# Set it as the auth token environment variable
export ANTHROPIC_AUTH_TOKEN=$(claude auth print-oauth-token)

# Run Society - it will use the OAuth token automatically
society
```

You can also pass it inline for a one-off session:

```bash
ANTHROPIC_AUTH_TOKEN=$(claude auth print-oauth-token) society
```

**How it works:** The Anthropic SDK accepts either `ANTHROPIC_API_KEY` (sent as `x-api-key` header) or `ANTHROPIC_AUTH_TOKEN` (sent as `Authorization: Bearer` header). If both are set, the SDK will use both — typically you only need one.

## Features

- **Persistent Agents** - Five distinct AI personas with their own roles, temperaments, and memories
- **Live Debates** - Watch agents argue, challenge, and build on each other's ideas
- **Consensus Building** - A facilitator agent synthesizes group positions
- **Memory System** - Agents remember past conversations and evolve over time
- **Dashboard TUI** - Rich terminal interface with agent cards, conversation panel, and memory inspector

## Agents

| Name | Role | Temperament |
|------|------|-------------|
| Aria | Systems Architect | Analytical |
| Rex | Critical Reviewer | Skeptical |
| Nova | Creative Thinker | Creative |
| Max | Pragmatic Engineer | Pragmatic |
| Sage | Discussion Facilitator | Diplomatic |

## Commands

Type in the input box:

- **Just type** - Ask all agents a question
- `/debate <topic>` - Start a multi-round debate
- `/ask @name question` - Ask a specific agent
- `/consensus` - Synthesize group consensus
- `/memories @name` - View an agent's memories

## Keyboard Shortcuts

- `Ctrl+D` - Start a debate
- `Ctrl+S` - Request consensus
- `Ctrl+M` - Cycle through agent memories
- `Ctrl+Q` - Quit

## Configuration

### Selecting agents

Spawn only specific agents:

```bash
society --agents architect critic creative
```

### Model

By default, Society uses `claude-sonnet-4-20250514`. The model can be changed in `src/society/llm.py`.
