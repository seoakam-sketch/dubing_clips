import logging
import shutil
from pathlib import Path

logger = logging.getLogger("clipdub.worker")


def remove_paths(*paths: str | Path | None) -> None:
    """Best-effort removal of intermediate files/dirs (raw audio, Demucs stems, etc.).

    Never raises: cleanup failures shouldn't fail a pipeline stage that already
    produced its real output.
    """
    for path in paths:
        if not path:
            continue
        p = Path(path)
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
            logger.info("cleanup.removed path=%s", p)
        except OSError:
            logger.warning("cleanup.failed path=%s", p, exc_info=True)
