import json
from pathlib import Path
from typing import Sequence

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field


class EditOperation(BaseModel):
    """A single search-and-replace operation on a file."""
    model_config = ConfigDict(extra="forbid")

    old_text: str = Field(
        description="Exact text to find in the file (byte-for-byte match)"
    )
    new_text: str = Field(
        description="Text to replace old_text with"
    )


async def edit_file(
    file_path: str,
    operations: list[dict],
    repo_path: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Edit a file using search-and-replace operations with automatic .bak backup.

    Accepts a list of {old_text, new_text} operations. All operations are validated
    before any are applied (atomic validation). Creates a .bak backup before editing.
    """
    try:
        # ── 1. Validate operations input ──
        if not operations:
            return json.dumps({
                "status": "error",
                "error": "No operations provided",
            })

        parsed_ops: list[EditOperation] = []
        for i, op_dict in enumerate(operations):
            try:
                parsed_ops.append(EditOperation(**op_dict))
            except Exception as e:
                return json.dumps({
                    "status": "error",
                    "error": f"Invalid operation format at index {i}: {e}",
                })

        # ── 2. Path resolution + traversal prevention ──
        path = Path(file_path).resolve()

        if repo_path is not None:
            resolved_repo = Path(repo_path).resolve()
            if not str(path).startswith(str(resolved_repo)):
                return json.dumps({
                    "status": "error",
                    "error": f"Path {file_path} resolves outside repository root",
                })

        # ── 3. File existence check ──
        if not path.exists():
            return json.dumps({
                "status": "error",
                "error": f"File not found: {file_path}",
            })

        # ── 4. Read original file ──
        try:
            original = path.read_text()
        except OSError as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
            })

        # ── 5. Validate ALL operations before applying ANY (D-16) ──
        for op in parsed_ops:
            if op.old_text not in original:
                return json.dumps({
                    "status": "error",
                    "error": (
                        f"old_text not found in file: {op.old_text[:60]}"
                        f"{'...' if len(op.old_text) > 60 else ''}"
                    ),
                })
            count = original.count(op.old_text)
            if count > 1:
                return json.dumps({
                    "status": "error",
                    "error": (
                        f"old_text appears {count} times in file. "
                        "Include more surrounding context for uniqueness."
                    ),
                })

        if ctx:
            await ctx.info(f"Editing {file_path} with {len(parsed_ops)} replacement(s)")

        # ── 6. Create .bak backup (D-14) ──
        backup_path = path.with_suffix(path.suffix + ".bak")
        if backup_path.exists():
            return json.dumps({
                "status": "error",
                "error": f"Backup file already exists: {backup_path}",
            })

        path.rename(backup_path)

        if ctx:
            await ctx.info(f"Backup created at {backup_path}")

        # ── 7. Apply all replacements (D-13, D-15) ──
        modified = original
        for op in parsed_ops:
            modified = modified.replace(op.old_text, op.new_text, 1)

        path.write_text(modified)

        if ctx:
            await ctx.info(f"Applied {len(parsed_ops)} replacement(s) to {file_path}")

        # ── 8. Return success ──
        return json.dumps({
            "status": "ok",
            "message": f"Applied {len(parsed_ops)} replacement(s) to {file_path}",
            "backup": str(backup_path),
        })

    except OSError as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Unexpected error: {e}",
        })
