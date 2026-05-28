"""Unit tests for command branch splitting."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from c2o.extract.command_branching import split_or_single
from c2o.extract.commands import _find_callback_node
from c2o.extract.param_schema import build_params_from_options
from c2o.parse.js import ParsedModule, collect_inline_object_pairs, find_calls, parse_source
from c2o.parse.literals import decode_js_value, pair_key


def _split(callback_source: str) -> tuple[list[str], str | None]:
    wrapped = dedent(f"""
        export function updateActions() {{
          this.setActionDefinitions({{
            stream: {{
              name: 'Stream',
              options: [
                {{
                  type: 'dropdown',
                  id: 'action',
                  choices: [{{ id: 'start' }}, {{ id: 'stop' }}, {{ id: 'Toggle' }}],
                }},
              ],
              callback: {callback_source}
            }},
          }})
        }}
        """)
    tree = parse_source(wrapped)

    parsed = ParsedModule(
        root=Path("."),
        sources={"actions.js": wrapped},
        trees={"actions.js": tree},
    )
    call = find_calls(parsed, "setActionDefinitions", include_methods=True)[0].node
    args = call.child_by_field_name("arguments")
    assert args is not None
    arg = args.named_children[0]
    action_obj = collect_inline_object_pairs(arg, wrapped)[0][1]
    callback = _find_callback_node(action_obj, wrapped)
    options = None
    for pair in action_obj.named_children:
        if pair.type != "pair":
            continue
        if pair_key(pair, wrapped) != "options":
            continue
        value = pair.child_by_field_name("value")
        if value is not None:
            options = decode_js_value(value, wrapped)
    assert callback is not None
    params = build_params_from_options(options)
    result = split_or_single(
        action_key="stream",
        label="Stream",
        options=options,
        callback_node=callback,
        source=wrapped,
        base_params=params,
    )
    return [candidate.command_key for candidate in result.candidates], result.state_dependent_reason


def test_if_chain_split_emits_start_and_stop() -> None:
    keys, reason = _split(dedent("""
            async (event) => {
              if (event.options.action === 'start') {
                this.socket.send('STREAM START\\n')
              } else if (event.options.action === 'stop') {
                this.socket.send('STREAM STOP\\n')
              }
            }
            """))

    assert keys == ["stream_start", "stream_stop"]
    assert reason is None


def test_instance_state_action_emits_flag_only() -> None:
    keys, reason = _split(dedent("""
            async () => {
              if (this.mute) {
                this.socket.send('MUTE OFF\\n')
              } else {
                this.socket.send('MUTE ON\\n')
              }
            }
            """))

    assert keys == []
    assert reason == "instance_state"


def test_prefix_suffix_split_emits_bmd_stream_commands() -> None:
    keys, reason = _split(dedent("""
            ({ options }) => {
              var cmd = 'STREAM STATE:\\nAction: '
              if (options.action === 'Toggle') {
                if (this.streaming === 'Streaming') {
                  cmd = cmd + 'Stop\\n\\n'
                } else {
                  cmd = cmd + 'Start\\n\\n'
                }
              } else {
                cmd = cmd + options.action + '\\n\\n'
              }
              this.sendCommand(cmd)
            }
            """))

    assert keys == ["stream_start", "stream_stop"]
    assert reason == "toggle_branch"
