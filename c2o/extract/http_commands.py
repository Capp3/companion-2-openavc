"""Extract OpenAVC HTTP command candidates from Companion action callbacks."""

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from c2o.model.driver import HttpMethod, ParamEntry
from c2o.parse.http_request import resolve_http_request_in_block


@dataclass(frozen=True)
class HttpCommandCandidate:
    """An HTTP command ready to merge into ``CommandsSection``."""

    command_key: str
    label: str
    method: HttpMethod
    path: str
    params: dict[str, ParamEntry]
    body: str | None = None
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None


def extract_http_command(
    *,
    action_key: str,
    label: str,
    callback_node: Node,
    source: str,
    base_params: dict[str, ParamEntry],
) -> HttpCommandCandidate | None:
    """Build one HTTP command candidate from a callback body, if possible."""
    body = _callback_body(callback_node)
    if body is None:
        return None

    request = resolve_http_request_in_block(body, source, set(base_params))
    if request is None:
        return None

    return HttpCommandCandidate(
        command_key=action_key,
        label=label,
        method=request.method,
        path=request.path,
        body=request.body,
        headers=request.headers,
        query_params=request.query_params,
        params=dict(base_params),
    )


def _callback_body(callback_node: Node) -> Node | None:
    if callback_node.type == "arrow_function":
        return callback_node.child_by_field_name("body")
    if callback_node.type in {"function", "function_expression"}:
        return callback_node.child_by_field_name("body")
    return None
