"""Helpers for resolving application assets in source and packaged builds."""

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return a path to a bundled resource."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        base_path = Path(bundle_root) / "assets"
    else:
        project_assets = Path(__file__).resolve().parents[3] / "assets"
        installed_assets = Path(sys.prefix) / "share" / "espress-view" / "assets"
        base_path = project_assets if project_assets.is_dir() else installed_assets
    return base_path.joinpath(*parts)
