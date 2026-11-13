"""AIBody companion: the "brain" side of the VaM AIBody plugin.

Runs outside of Virt-A-Mate on the same PC. Captures the microphone, detects speech,
turns it into text, asks a language model for a reply, synthesizes speech and sends
commands to the VaM plugin. See ../protocol/PROTOCOL.md.
"""

__version__ = "0.1.0"
PROTOCOL_VERSION = 1
