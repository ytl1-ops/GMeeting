"""Fabrique de vrais fichiers Outlook .msg (conteneur OLE conforme MS-OXMSG) pour les tests, via l'écrivain OLE d'extract-msg."""
from __future__ import annotations

import struct
from datetime import datetime, timezone

from extract_msg.ole_writer import OleWriter

PT_LONG, PT_UNICODE, PT_BINARY, PT_SYSTIME = 0x0003, 0x001F, 0x0102, 0x0040


def _u(s: str) -> bytes:
    return s.encode("utf-16-le")


def build_msg(path, subject: str, sender: str, to: str, body: str, when: datetime, cc: str = "",
              attachments: list[tuple[str, bytes]] | None = None) -> None:
    attachments = attachments or []
    w = OleWriter()
    props = b""
    streams = {0x001A: "IPM.Note", 0x0037: subject, 0x0C1A: sender, 0x5D01: "sender@example.org", 0x0E04: to, 0x0E03: cc, 0x1000: body}
    for tag, text in streams.items():
        data = _u(text)
        w.addEntry(f"__substg1.0_{tag:04X}{PT_UNICODE:04X}", data)
        props += struct.pack("<IIII", (tag << 16) | PT_UNICODE, 6, len(data) + 2, 0)   # taille = octets + terminateur nul
    ft = int((when.astimezone(timezone.utc).timestamp() + 11644473600) * 10_000_000)
    props += struct.pack("<IIQ", (0x0039 << 16) | PT_SYSTIME, 6, ft)
    header = struct.pack("<8sIIII8s", b"", len(attachments), len(attachments), 0, len(attachments), b"")
    w.addEntry("__properties_version1.0", header + props)
    w.addEntry("__nameid_version1.0", storage=True)
    for n in ("00020102", "00030102", "00040102"):
        w.addEntry(f"__nameid_version1.0/__substg1.0_{n}", b"")
    for i, (name, data) in enumerate(attachments):
        base = f"__attach_version1.0_#{i:08X}"
        w.addEntry(base, storage=True)
        w.addEntry(f"{base}/__substg1.0_3707{PT_UNICODE:04X}", _u(name))
        w.addEntry(f"{base}/__substg1.0_3704{PT_UNICODE:04X}", _u(name[:8]))
        w.addEntry(f"{base}/__substg1.0_3701{PT_BINARY:04X}", data)
        ap = struct.pack("<8s", b"")
        ap += struct.pack("<IIII", (0x3705 << 16) | PT_LONG, 6, 1, 0)                       # pièce jointe par valeur
        ap += struct.pack("<IIII", (0x3707 << 16) | PT_UNICODE, 6, len(_u(name)) + 2, 0)
        ap += struct.pack("<IIII", (0x3701 << 16) | PT_BINARY, 6, len(data), 0)
        w.addEntry(f"{base}/__properties_version1.0", ap)
    w.write(str(path))
