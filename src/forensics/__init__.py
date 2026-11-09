"""failure-forensics — observability + RCA for multi-step AI pipelines."""

from importlib import metadata

try:
    __version__ = metadata.version("failure-forensics")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
