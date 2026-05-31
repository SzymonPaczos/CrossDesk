"""Generated gRPC / protobuf stubs.

The protoc output under ``crossdesk/v1/`` uses absolute imports rooted at the
proto package (e.g. ``from crossdesk.v1 import common_pb2``), so this directory
must be on ``sys.path`` for the stubs to import one another at runtime.
``conftest.py`` inserts it for the test suite; doing the same here means the
installed ``crossdesk`` / ``crossdesk-host`` entry points resolve the stubs
too — without it any CLI command crashes with ``ModuleNotFoundError: No module
named 'crossdesk'`` as soon as the import chain reaches a ``*_pb2`` module.
"""
import os
import sys

_PROTO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROTO_ROOT not in sys.path:
    sys.path.insert(0, _PROTO_ROOT)
