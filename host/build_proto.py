"""Regenerate Python protobuf + gRPC + mypy stubs from `proto/`.

Run from the repo root or from `host/`:

    python host/build_proto.py
"""

import glob
import os
import sys
from pathlib import Path

from grpc_tools import protoc


def main() -> int:
    root_dir = Path(__file__).parent.parent
    proto_dir = root_dir / "proto"
    out_dir = root_dir / "host" / "src" / "crossdesk_host" / "proto"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "__init__.py").touch(exist_ok=True)

    proto_files = sorted(glob.glob(str(proto_dir / "crossdesk" / "v1" / "*.proto")))
    if not proto_files:
        print("No proto files found!", file=sys.stderr)
        return 1

    print(f"Generating Python protobuf code in {out_dir}…")

    import grpc_tools

    well_known_protos_include = os.path.join(
        os.path.dirname(grpc_tools.__file__), "_proto"
    )

    protoc_args = [
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"-I{well_known_protos_include}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        # mypy-protobuf produces *_pb2.pyi / *_pb2_grpc.pyi alongside the
        # generated modules so mypy --strict can see message field types.
        f"--mypy_out={out_dir}",
        f"--mypy_grpc_out={out_dir}",
        *proto_files,
    ]

    code = protoc.main(protoc_args)
    if code != 0:
        print(f"protoc failed with exit code {code}", file=sys.stderr)
        return code

    # grpc_tools emits flat imports (`import common_pb2 as …`) instead of the
    # package-qualified form Python 3 needs. Mark the package directories so
    # imports resolve under `crossdesk_host.proto.crossdesk.v1.*`.
    for sub in (out_dir / "crossdesk", out_dir / "crossdesk" / "v1"):
        if sub.exists():
            (sub / "__init__.py").touch(exist_ok=True)

    print("Generation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
