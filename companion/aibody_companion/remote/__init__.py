"""Remote control of the one AIBody character (version 31): a local web page / HTTP API and an OSC listener.

Off by default (config.json remote.enabled). Both servers bind 127.0.0.1 ONLY, so they are reachable from this
computer and from nowhere else; they run on their own threads and only put validated actions into a queue that the
app's main loop runs (RemoteControl.process), exactly like the file / socket transports hand over plugin events.
Nothing here talks to VaM directly: every action becomes the same command the AI or the plugin menu would produce.
See docs/REMOTE.md.
"""
from .core import ACTIONS, RemoteControl, RemoteError, parse_action

__all__ = ["ACTIONS", "RemoteControl", "RemoteError", "parse_action"]
