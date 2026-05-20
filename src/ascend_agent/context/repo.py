import pathlib

from ascend_agent.context.models import RepoInfo


class RepoScanner:

    def scan(self, path: str | pathlib.Path) -> RepoInfo:
        resolved = pathlib.Path(path).resolve()
        root = resolved

        gitignore_patterns = self._load_gitignore(root)

        structure = []
        for py_file in sorted(root.rglob("*.py")):
            rel = py_file.relative_to(root)
            parts = rel.parts
            if any(
                p.startswith(".") or p == "__pycache__" or p == "node_modules" or p == ".venv"
                for p in parts[:-1]
            ):
                continue
            rel_str = str(rel.as_posix())
            if self._is_gitignored(rel_str, gitignore_patterns):
                continue
            structure.append(rel_str)

        return RepoInfo(
            path=str(resolved),
            language="python",
            file_count=len(structure),
            structure=structure,
        )

    def _load_gitignore(self, root: pathlib.Path) -> list[str]:
        gitignore_path = root / ".gitignore"
        if not gitignore_path.exists():
            return []
        patterns = []
        for line in gitignore_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        return patterns

    def _is_gitignored(self, rel_path: str, patterns: list[str]) -> bool:
        for pat in patterns:
            if pat.startswith("/"):
                if pathlib.PurePosixPath(rel_path).match(pat[1:]):
                    return True
            else:
                if pathlib.PurePosixPath(rel_path).match(pat):
                    return True
        return False
