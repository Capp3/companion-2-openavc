"""Extract OpenAVC polling queries from Companion setInterval handlers."""

from __future__ import annotations

from c2o.model.driver import PollingSection
from c2o.model.review import ReviewReport
from c2o.parse.js import ParsedModule
from c2o.parse.polling_handlers import find_polling_handlers, infer_poll_interval_seconds
from c2o.parse.send_template import resolve_all_static_sends


class PollingExtractionError(ValueError):
    """Raised when polling extraction encounters unrecoverable malformed input."""


def extract_polling(parsed: ParsedModule) -> tuple[PollingSection, ReviewReport]:
    """Build polling queries and optional inferred poll cadence from setInterval handlers."""
    handlers = find_polling_handlers(parsed)
    queries: list[str] = []
    inferred_interval: int | None = None

    for handler in handlers:
        queries.extend(resolve_all_static_sends(handler.callback_body, handler.source))
        if inferred_interval is None:
            inferred_interval = infer_poll_interval_seconds(handler.delay_ms_node, handler.source)

    return (
        PollingSection(
            queries=tuple(queries),
            inferred_poll_interval=inferred_interval,
        ),
        ReviewReport(),
    )
