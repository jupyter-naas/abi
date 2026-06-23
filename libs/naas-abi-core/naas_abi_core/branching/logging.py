"""Logging integration: tag every record with the active branch.

Install :class:`BranchContextLogFilter` once on the root logger (or on
specific loggers) and every emitted ``LogRecord`` gains a ``branch``
attribute. Format strings can then reference ``%(branch)s``.

Example
-------

::

    import logging
    from naas_abi_core.branching import BranchContextLogFilter

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(branch)s] %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(BranchContextLogFilter())
    logging.getLogger().addHandler(handler)

The filter never rejects records — it only annotates them. ``filter``
returns ``True`` unconditionally.
"""

from __future__ import annotations

import logging

from .context import BranchContext


class BranchContextLogFilter(logging.Filter):
    """Annotate every ``LogRecord`` with ``record.branch``.

    Read at filter time (not at emit time), so records logged inside a
    ``BranchContext.use(...)`` block carry the correct branch even if
    the formatter runs later in a different context. This matches how
    ``LoggerAdapter.extra`` is conventionally captured.
    """

    def __init__(self, *, attribute: str = "branch") -> None:
        """Customize the record attribute name if ``branch`` collides
        with another extension. Defaults to ``branch`` everywhere
        ``naas_abi_core`` ships."""
        super().__init__()
        self._attribute = attribute

    def filter(self, record: logging.LogRecord) -> bool:
        # setattr (vs assignment) avoids overriding a value already set
        # via LoggerAdapter.extra={"branch": ...} — explicit tagging
        # wins over implicit ambient capture.
        if not hasattr(record, self._attribute):
            setattr(record, self._attribute, BranchContext.current())
        return True
