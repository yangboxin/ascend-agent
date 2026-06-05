"""Load user-defined skill definitions from the config directory.

Skills are Markdown files with YAML frontmatter, stored in
``~/.config/ascend-agent/skills/``.  Each skill defines prompt content
that the runtime injects into the system prompt when relevant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_SKILLS_DIR_NAME = "skills"
_FRONTMATTER_DELIMITER = "---"


@dataclass
class Skill:
    """A loaded skill definition."""

    name: str
    description: str = ""
    content: str = ""
    when_to_use: str = ""
    source: str = ""


def load_skills(config_dir: str | Path = "") -> list[Skill]:
    """Load all skills from the user's skill directory.

    Args:
        config_dir: Root config directory. Defaults to
            ``~/.config/ascend-agent``.

    Returns:
        List of parsed Skill objects (may be empty if no skills found).
    """
    root = Path(config_dir) if config_dir else _default_config_dir()
    skills_dir = root / _SKILLS_DIR_NAME
    if not skills_dir.is_dir():
        return []

    skills: list[Skill] = []
    for path in sorted(skills_dir.glob("*.md")):
        skill = _parse_skill_file(path)
        if skill:
            skills.append(skill)
    return skills


def skill_prompt_injection(skills: list[Skill]) -> str:
    """Build the system-prompt section for available skills.

    Only includes metadata (name, description, when_to_use) so the model
    knows what's available without bloating the prompt with full content.
    """
    if not skills:
        return ""
    lines = ["## Available Skills"]
    for skill in skills:
        lines.append(f"- **{skill.name}**: {skill.description}")
        if skill.when_to_use:
            lines.append(f"  When to use: {skill.when_to_use}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_config_dir() -> Path:
    return Path.home() / ".config" / "ascend-agent"


def _parse_skill_file(path: Path) -> Skill | None:
    """Parse a skill markdown file with YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    if frontmatter is None:
        logger.warning("Skill file %s has no frontmatter, skipping.", path)
        return None

    try:
        meta: dict[str, Any] = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML frontmatter in %s: %s", path, exc)
        return None

    name = meta.get("name") or path.stem
    return Skill(
        name=str(name),
        description=str(meta.get("description", "")),
        content=body.strip(),
        when_to_use=str(meta.get("when_to_use", "")),
        source=str(path),
    )


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split YAML frontmatter from body.  Returns (frontmatter, body)."""
    if not text.startswith(_FRONTMATTER_DELIMITER):
        return None, text
    # Find the closing delimiter
    end_idx = text.find(_FRONTMATTER_DELIMITER, len(_FRONTMATTER_DELIMITER))
    if end_idx == -1:
        return None, text
    frontmatter = text[len(_FRONTMATTER_DELIMITER):end_idx].strip()
    body = text[end_idx + len(_FRONTMATTER_DELIMITER):].strip()
    return frontmatter, body
