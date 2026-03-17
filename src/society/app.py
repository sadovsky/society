"""Textual TUI application for Society."""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from society.models import Agent, AgentStatus, Memory, Message
from society.society import Society


class AgentCard(Widget):
    """Displays an agent's status, role, and recent activity."""

    DEFAULT_CSS = """
    AgentCard {
        height: auto;
        min-height: 5;
        margin: 0 0 1 0;
        padding: 1;
        border: round $surface-lighten-2;
        background: $surface;
    }
    AgentCard .agent-name {
        text-style: bold;
        width: 100%;
    }
    AgentCard .agent-role {
        color: $text-muted;
    }
    AgentCard .agent-status {
        dock: right;
        width: auto;
    }
    AgentCard .agent-msgs {
        color: $text-muted;
    }
    """

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        yield Label(f"  {self.agent.name}", classes="agent-name")
        yield Label(self.agent.config.role, classes="agent-role")
        yield Label(
            f"{self.agent.config.temperament.value} | {self.agent.message_count} msgs",
            classes="agent-msgs",
        )
        yield Label(self._status_icon(), classes="agent-status")

    def _status_icon(self) -> str:
        icons = {
            AgentStatus.IDLE: "[-] idle",
            AgentStatus.THINKING: "[*] thinking...",
            AgentStatus.SPEAKING: "[>] speaking...",
            AgentStatus.LISTENING: "[~] listening",
        }
        return icons.get(self.agent.status, "[-] idle")

    def refresh_status(self) -> None:
        try:
            status_label = self.query_one(".agent-status", Label)
            status_label.update(self._status_icon())
            msgs_label = self.query_one(".agent-msgs", Label)
            msgs_label.update(
                f"{self.agent.config.temperament.value} | {self.agent.message_count} msgs"
            )
        except NoMatches:
            pass


class AgentSidebar(Widget):
    """Left sidebar showing all agent cards."""

    DEFAULT_CSS = """
    AgentSidebar {
        width: 30;
        min-width: 28;
        border-right: tall $surface-lighten-2;
        padding: 1;
    }
    AgentSidebar .sidebar-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: $accent;
    }
    """

    def __init__(self, society: Society) -> None:
        super().__init__()
        self.society = society

    def compose(self) -> ComposeResult:
        yield Label("AGENTS", classes="sidebar-title")
        for agent in self.society.agents.values():
            yield AgentCard(agent)

    def refresh_agents(self) -> None:
        for card in self.query(AgentCard):
            card.refresh_status()


class ConversationPanel(Widget):
    """Main panel showing the conversation/debate."""

    DEFAULT_CSS = """
    ConversationPanel {
        height: 1fr;
        border: round $surface-lighten-2;
    }
    """

    AGENT_COLORS = {}

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, wrap=True, id="conversation-log")

    def add_message(self, message: Message, color: str = "white") -> None:
        try:
            log = self.query_one("#conversation-log", RichLog)
            if message.agent_name == "You":
                log.write(f"\n[bold cyan]You:[/bold cyan] {message.content}")
            else:
                log.write(
                    f"\n[bold {color}]{message.agent_name}:[/bold {color}] {message.content}"
                )
        except NoMatches:
            pass


class MemoryPanel(Widget):
    """Panel showing agent memories."""

    DEFAULT_CSS = """
    MemoryPanel {
        height: 1fr;
        border: round $surface-lighten-2;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, wrap=True, id="memory-log")

    def show_memories(self, agent: Agent) -> None:
        try:
            log = self.query_one("#memory-log", RichLog)
            log.clear()
            log.write(f"[bold]{agent.name}'s Memories[/bold]\n")
            memories = agent.recent_memories(20)
            if not memories:
                log.write("[dim]No memories yet.[/dim]")
                return
            for m in memories:
                importance = "!" * int(m.importance * 5)
                log.write(f"  [{m.source}] {importance} {m.summary()}")
        except NoMatches:
            pass


class SocietyApp(App):
    """The Society TUI application."""

    TITLE = "Society"
    SUB_TITLE = "Multi-Agent Collaboration"

    CSS = """
    Screen {
        layout: horizontal;
    }
    #main-area {
        width: 1fr;
        layout: vertical;
    }
    #input-area {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    #input-box {
        width: 1fr;
    }
    #tabs {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+d", "start_debate", "Debate"),
        Binding("ctrl+s", "consensus", "Consensus"),
        Binding("ctrl+m", "cycle_memories", "Memories"),
    ]

    def __init__(self, society: Society | None = None) -> None:
        super().__init__()
        if society is not None:
            self.society = society
        else:
            self.society = Society()
            self.society.spawn_default_society()
        self._memory_agent_idx = 0

        # Wire up callbacks
        self.society.on_message(self._handle_message)
        self.society.on_status_change(self._handle_status_change)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield AgentSidebar(self.society)
            with Vertical(id="main-area"):
                with TabbedContent(id="tabs"):
                    with TabPane("Conversation", id="tab-conv"):
                        yield ConversationPanel()
                    with TabPane("Memories", id="tab-mem"):
                        yield MemoryPanel()
                with Horizontal(id="input-area"):
                    yield Input(
                        placeholder="Ask the society... (/debate <topic> | /ask @agent question | /consensus)",
                        id="input-box",
                    )
        yield Footer()

    def on_mount(self) -> None:
        try:
            conv = self.query_one(ConversationPanel)
            log = conv.query_one("#conversation-log", RichLog)
            log.write("[bold green]Welcome to Society![/bold green]")
            log.write("A multi-agent system running in your terminal.\n")
            log.write(f"[dim]{len(self.society.agents)} agents spawned and ready.[/dim]")
            log.write("")
            log.write("[dim]Commands:[/dim]")
            log.write("  [cyan]/debate <topic>[/cyan]  - Start a multi-round debate")
            log.write("  [cyan]/ask @name msg[/cyan]   - Ask a specific agent")
            log.write("  [cyan]/consensus[/cyan]       - Synthesize group consensus")
            log.write("  [cyan]/memories @name[/cyan]  - View an agent's memories")
            log.write("  Or just type a question for all agents.\n")
        except NoMatches:
            pass

    def _handle_message(self, message: Message) -> None:
        try:
            conv = self.query_one(ConversationPanel)
            color = "white"
            if message.agent_name in self.society.agents:
                color = self.society.agents[message.agent_name].color
            conv.add_message(message, color)
        except NoMatches:
            pass

    def _handle_status_change(self, agent_name: str, status: AgentStatus) -> None:
        try:
            sidebar = self.query_one(AgentSidebar)
            sidebar.refresh_agents()
        except NoMatches:
            pass

    @on(Input.Submitted, "#input-box")
    async def handle_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        if text.startswith("/debate "):
            topic = text[8:].strip()
            if topic:
                self._run_debate(topic)
        elif text.startswith("/ask @"):
            parts = text[6:].split(None, 1)
            if len(parts) == 2:
                name, question = parts
                # Find agent by name (case-insensitive)
                agent_name = None
                for n in self.society.agents:
                    if n.lower() == name.lower():
                        agent_name = n
                        break
                if agent_name:
                    self._run_ask(question, agent_name)
                else:
                    self._show_error(f"Agent '{name}' not found.")
            else:
                self._show_error("Usage: /ask @name your question")
        elif text == "/consensus":
            self._run_consensus()
        elif text.startswith("/memories"):
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith("@"):
                name = parts[1][1:]
                for n, agent in self.society.agents.items():
                    if n.lower() == name.lower():
                        self._show_memories(agent)
                        break
            else:
                self.action_cycle_memories()
        else:
            # General question to all agents
            self._run_ask(text)

    @work(thread=False)
    async def _run_ask(self, question: str, agent_name: str | None = None) -> None:
        await self.society.ask(question, agent_name)

    @work(thread=False)
    async def _run_debate(self, topic: str) -> None:
        await self.society.debate(topic, rounds=3)

    @work(thread=False)
    async def _run_consensus(self) -> None:
        await self.society.consensus("the current discussion")

    def _show_error(self, text: str) -> None:
        try:
            conv = self.query_one(ConversationPanel)
            log = conv.query_one("#conversation-log", RichLog)
            log.write(f"[bold red]{text}[/bold red]")
        except NoMatches:
            pass

    def _show_memories(self, agent: Agent) -> None:
        try:
            mem_panel = self.query_one(MemoryPanel)
            mem_panel.show_memories(agent)
            tabs = self.query_one(TabbedContent)
            tabs.active = "tab-mem"
        except NoMatches:
            pass

    def action_start_debate(self) -> None:
        """Triggered by Ctrl+D binding."""
        try:
            input_box = self.query_one("#input-box", Input)
            input_box.value = "/debate "
            input_box.focus()
        except NoMatches:
            pass

    def action_consensus(self) -> None:
        """Triggered by Ctrl+S binding."""
        self._run_consensus()

    def action_cycle_memories(self) -> None:
        """Cycle through agent memories."""
        agents = list(self.society.agents.values())
        if not agents:
            return
        agent = agents[self._memory_agent_idx % len(agents)]
        self._memory_agent_idx += 1
        self._show_memories(agent)
