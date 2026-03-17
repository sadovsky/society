# Society

A terminal-native multi-agent system where persistent AI personas collaborate, debate, specialize, and evolve over time.

## Quick Start

```bash
# Install
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY=your-key-here

# Run
society
```

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
