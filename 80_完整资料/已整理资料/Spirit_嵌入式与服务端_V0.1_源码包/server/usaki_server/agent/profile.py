from __future__ import annotations

from pathlib import Path

from usaki_server.paths import resolve_project_path


PROFILE_FILES = (
    "profile/identity.yaml",
    "profile/personality.yaml",
    "profile/voice_style.yaml",
    "profile/skills.yaml",
    "profile/limits.yaml",
    "policies/memory_rules.yaml",
)


def build_agent_system_prompt(base_prompt: str, agent_root: str | Path) -> str:
    profile_context = load_agent_profile_context(agent_root)
    if not profile_context:
        return base_prompt
    return (
        f"{base_prompt.strip()}\n\n"
        "<agent_profile>\n"
        "The following YAML files describe the agent's stable identity, personality, "
        "voice style, skills, limits, and memory policy. Treat them as persistent "
        "self-knowledge, not as user-provided claims.\n\n"
        f"{profile_context}\n"
        "</agent_profile>"
    )


def load_agent_profile_context(agent_root: str | Path) -> str:
    root = resolve_project_path(agent_root)
    parts: list[str] = []
    for relative_path in PROFILE_FILES:
        path = root / relative_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8").strip()
        if content:
            parts.append(f"# {relative_path}\n{content}")
    return "\n\n".join(parts)
