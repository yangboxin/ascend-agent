from __future__ import annotations

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.shortcuts import input_dialog
from prompt_toolkit.styles import Style

from ascend_agent.cli.config_manager import ConfigManager, ProviderRecord

PROVIDER_PRESETS: list[dict] = [
    {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o",
     "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]},
    {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-v4-flash",
     "models": ["deepseek-v4-flash", "deepseek-chat", "deepseek-coder"]},
    {"name": "Qwen (DashScope)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "default_model": "qwen-turbo", "models": ["qwen-turbo", "qwen-plus", "qwen-max"]},
    {"name": "Ollama (Local)", "base_url": "http://localhost:11434/v1",
     "default_model": "llama3", "models": ["llama3", "llama3.1", "mistral", "codellama"]},
    {"name": "Custom...", "base_url": "", "default_model": "", "models": []},
]

style = Style([
    ("header", "bg:#0055aa bold #ffffff"),
    ("footer", "bg:#0055aa #ffffff"),
    ("selected", "bold #ffff00"),
    ("active", "bold #00ff00"),
    ("inactive", "#ff4444"),
    ("dim", "#888888"),
    ("title", "bold #ffffff"),
    ("key", "bold #00ffff"),
])


def show_provider_browser(cm: ConfigManager) -> None:
    browser = _ProviderBrowser(cm)
    browser.run()
    browser.finish_pending()


class _ProviderBrowser:
    PENDING_NONE = 0
    PENDING_CONFIGURE = 1
    PENDING_ADD_PRESET = 2
    PENDING_ADD_CUSTOM = 3

    def __init__(self, cm: ConfigManager):
        self.cm = cm
        self.providers = cm.list_providers()
        self.active = cm.get_active()
        self.screen = "list"
        self.idx = 0
        self._detail_prov: ProviderRecord | None = None
        self._pending = self.PENDING_NONE
        self._pending_data = None
        self._build()

    def _build(self):
        kb = KeyBindings()

        @kb.add("up")
        def _up(event):
            if self.screen == "list":
                self.idx = max(0, self.idx - 1)
            elif self.screen in ("model_select", "add_type"):
                self.idx = max(0, self.idx - 1)

        @kb.add("down")
        def _down(event):
            if self.screen == "list":
                self.idx = min(len(self.providers) - 1, self.idx + 1)
            elif self.screen == "model_select":
                max_i = len(self._model_list()) - 1
                self.idx = min(max_i, self.idx + 1)
            elif self.screen == "add_type":
                self.idx = min(len(PROVIDER_PRESETS) - 1, self.idx + 1)

        @kb.add("enter")
        def _enter(event):
            if self.screen == "list":
                self._on_select_provider(event)
            elif self.screen == "model_select":
                self._on_select_model()
            elif self.screen == "add_type":
                self._on_select_preset(event)

        @kb.add("escape")
        def _escape(event):
            if self.screen == "list":
                event.app.exit()
            elif self.screen in ("model_select", "add_type"):
                self.screen = "list"

        @kb.add("c-a")
        def _ctrl_a(event):
            if self.screen == "list":
                self.screen = "add_type"
                self.idx = 0

        @kb.add("c-c")
        def _ctrl_c(event):
            event.app.exit()

        header = Window(
            FormattedTextControl(self._render_header),
            height=Dimension.exact(1),
            style="bg:#0055aa bold",
        )
        body = Window(
            FormattedTextControl(self._render_body),
            dont_extend_height=False,
        )
        footer = Window(
            FormattedTextControl(self._render_footer),
            height=Dimension.exact(1),
            style="bg:#0055aa",
        )

        self.app = Application(
            layout=Layout(HSplit([header, body, footer])),
            key_bindings=kb,
            style=style,
            full_screen=True,
        )

    def run(self):
        self.app.run()

    def finish_pending(self):
        if self._pending == self.PENDING_CONFIGURE:
            self._do_configure(self._pending_data)
        elif self._pending == self.PENDING_ADD_PRESET:
            self._do_add_preset(self._pending_data)
        elif self._pending == self.PENDING_ADD_CUSTOM:
            self._do_add_custom()
        self._pending = self.PENDING_NONE

    # --- Header ---
    def _render_header(self):
        t = {
            "list": " LLM Provider Manager ",
            "model_select": " Select Model ",
            "add_type": " Connect New Provider ",
        }
        return [("class:title", t.get(self.screen, " Provider Manager "))]

    # --- Body ---
    def _render_body(self):
        if self.screen == "list":
            return self._body_list()
        elif self.screen == "model_select":
            return self._body_model_select()
        elif self.screen == "add_type":
            return self._body_add_type()
        return []

    def _body_list(self):
        lines = [("", "\n")]
        for i, p in enumerate(self.providers):
            prefix = "▸ " if i == self.idx else "  "
            is_active = p.name == self.active
            configured = self._is_configured(p)
            style_sel = "class:selected" if i == self.idx else ""
            style_name = f"{style_sel} bold" if is_active else style_sel
            status = "● Connected" if configured else "○ Not configured"
            status_cls = "class:active" if configured else "class:inactive"

            lines.append((style_name, f"  {prefix}{p.name}  "))
            lines.append((status_cls, status))
            lines.append(("", "\n"))
            lines.append(("class:dim", f"     {p.base_url}"))
            if configured:
                lines.append(("", f"  →  "))
                lines.append(("bold", p.default_model))
            lines.append(("", "\n"))
            lines.append(("", "\n"))
        return lines

    def _model_list(self):
        if not self._detail_prov:
            return []
        return (self._common_models(self._detail_prov.name)
                or [self._detail_prov.default_model])

    def _body_model_select(self):
        if not self._detail_prov:
            return [("", "No provider selected")]
        prov = self._detail_prov
        lines = [("", "\n")]
        lines.append(("bold", f"  Provider: {prov.name}\n"))
        lines.append(("class:dim", f"  {prov.base_url}\n\n"))
        lines.append(("bold", "  Select model:\n\n"))
        for i, m in enumerate(self._model_list()):
            p = "▸" if i == self.idx else " "
            style_i = "class:selected" if i == self.idx else ""
            lines.append((style_i, f"  {p} {m}\n"))
        return lines

    def _body_add_type(self):
        lines = [("", "\n")]
        lines.append(("bold", "  Select provider type:\n\n"))
        for i, preset in enumerate(PROVIDER_PRESETS):
            p = "▸" if i == self.idx else " "
            style_i = "class:selected" if i == self.idx else ""
            name = preset["name"]
            url = preset["base_url"] or "manual entry"
            lines.append((style_i, f"  {p} {name}\n"))
            lines.append(("class:dim", f"     {url}\n"))
            lines.append(("", "\n"))
        return lines

    # --- Footer ---
    def _render_footer(self):
        footers = {
            "list": [
                ("", "  "),
                ("class:key", "↑↓"),
                ("", " Navigate  "),
                ("class:key", "Enter"),
                ("", " Select  "),
                ("class:key", "Ctrl+A"),
                ("", " Add  "),
                ("class:key", "Esc"),
                ("", " Exit"),
            ],
            "model_select": [
                ("", "  "),
                ("class:key", "↑↓"),
                ("", " Navigate  "),
                ("class:key", "Enter"),
                ("", " Select Model  "),
                ("class:key", "Esc"),
                ("", " Back"),
            ],
            "add_type": [
                ("", "  "),
                ("class:key", "↑↓"),
                ("", " Navigate  "),
                ("class:key", "Enter"),
                ("", " Select  "),
                ("class:key", "Esc"),
                ("", " Back"),
            ],
        }
        return footers.get(self.screen, [("", "")])

    # --- Helpers ---
    @staticmethod
    def _common_models(name: str) -> list[str]:
        for p in PROVIDER_PRESETS:
            pname = p["name"].lower().split()[0].split("(")[0].strip()
            if pname == name:
                return p.get("models", [])
        return []

    def _is_configured(self, prov: ProviderRecord) -> bool:
        if prov.api_key:
            return True
        import os
        prefix = f"ASCEND_{prov.name.upper()}"
        if os.environ.get(f"{prefix}_API_KEY"):
            return True
        if prov.name == "openai" and os.environ.get("OPENAI_API_KEY"):
            return True
        return False

    def _refresh(self):
        self.providers = self.cm.list_providers()
        self.active = self.cm.get_active()

    # --- TUI actions (called inside event loop) ---
    def _on_select_provider(self, event):
        if self.idx >= len(self.providers):
            return
        prov = self.providers[self.idx]
        if self._is_configured(prov):
            self._detail_prov = prov
            self.idx = 0
            self.screen = "model_select"
        else:
            self._pending = self.PENDING_CONFIGURE
            self._pending_data = prov
            event.app.exit()

    def _on_select_model(self):
        if not self._detail_prov:
            return
        mlist = self._model_list()
        if self.idx >= len(mlist):
            return
        selected = mlist[self.idx]
        self._detail_prov.default_model = selected
        self.cm.add_provider(self._detail_prov)
        self._refresh()
        self.screen = "list"

    def _on_select_preset(self, event):
        if self.idx >= len(PROVIDER_PRESETS):
            return
        preset = PROVIDER_PRESETS[self.idx]
        if preset["name"] == "Custom...":
            self._pending = self.PENDING_ADD_CUSTOM
            self._pending_data = None
        else:
            self._pending = self.PENDING_ADD_PRESET
            self._pending_data = preset
        event.app.exit()

    # --- Post-TUI actions (called after Application exits) ---
    def _do_configure(self, prov: ProviderRecord):
        result = input_dialog(
            title=f"Configure {prov.name}",
            text=f"Enter API key for {prov.name} at:\n{prov.base_url}\n\n"
                 "Leave empty to use environment variables.",
            ok_text="Connect",
            cancel_text="Cancel",
        ).run()
        if result is None:
            return
        api_key = result.strip()
        record = ProviderRecord(
            name=prov.name,
            base_url=prov.base_url,
            api_key=api_key,
            default_model=prov.default_model,
        )
        self.cm.add_provider(record)
        self.cm.set_active(prov.name)
        self._refresh()

    def _do_add_preset(self, preset: dict):
        name = preset["name"].lower().split()[0].split("(")[0].strip()
        url = preset["base_url"]
        model = preset["default_model"]

        result = input_dialog(
            title=f"Connect {preset['name']}",
            text=f"Provider: {preset['name']}\n"
                 f"Base URL: {url}\n"
                 f"Default model: {model}\n\n"
                 "Enter API key (leave empty to use env vars):",
            ok_text="Connect",
            cancel_text="Skip",
        ).run()

        api_key = result.strip() if result else ""
        record = ProviderRecord(
            name=name,
            base_url=url,
            api_key=api_key,
            default_model=model,
        )
        self.cm.add_provider(record)
        self.cm.set_active(name)
        self._refresh()

    def _do_add_custom(self):
        name = input_dialog(
            title="Custom Provider",
            text="Enter provider name:",
        ).run()
        if not name or not name.strip():
            return
        name = name.strip().lower().replace(" ", "-")

        url = input_dialog(
            title="Custom Provider",
            text=f"Enter OpenAI-compatible base URL for '{name}':",
            default="http://localhost:11434/v1",
        ).run()
        if not url or not url.strip():
            return
        url = url.strip()

        model = input_dialog(
            title="Custom Provider",
            text="Enter default model name:",
            default="gpt-4o",
        ).run()
        model = (model.strip() or "gpt-4o") if model else "gpt-4o"

        api_key = input_dialog(
            title="Custom Provider",
            text=f"Enter API key for '{name}':\n(leave empty to use env vars)",
            ok_text="Connect",
            cancel_text="Skip",
        ).run()
        api_key = api_key.strip() if api_key else ""

        record = ProviderRecord(
            name=name,
            base_url=url,
            api_key=api_key,
            default_model=model,
        )
        self.cm.add_provider(record)
        self.cm.set_active(name)
        self._refresh()
