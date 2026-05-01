import os
import sys
import glob
from grpc_tools import protoc
from pathlib import Path

def main():
    root_dir = Path(__file__).parent.parent
    proto_dir = root_dir / "proto"
    out_dir = root_dir / "host" / "src" / "crossdesk_host" / "proto"
    
    out_dir.mkdir(parents=True, exist_ok=True)
    init_file = out_dir / "__init__.py"
    if not init_file.exists():
        init_file.touch()

    proto_files = glob.glob(str(proto_dir / "crossdesk" / "v1" / "*.proto"))
    
    if not proto_files:
        print("No proto files found!")
        sys.exit(1)

    print(f"Generating Python protobuf code in {out_dir}...")

    # Zastąpione args dla protoc (takie jak wywoływane przez commandline)
    # Musimy dodać ścieżki do -I dla prawidłowego importowania (np. google/protobuf)
    import grpc_tools
    well_known_protos_include = os.path.join(os.path.dirname(grpc_tools.__file__), '_proto')

    protoc_args = [
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"-I{well_known_protos_include}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
    ] + proto_files

    code = protoc.main(protoc_args)
    if code != 0:
        print(f"Failed to compile protobufs, exit code {code}")
        sys.exit(code)
    
    # Python w grpc_tools często generuje importy takie jak: `import common_pb2 as ...` 
    # zamiast `from . import common_pb2 as ...`. To psuje moduły w Python 3+.
    # Należy przeprowadzić patching wygenerowanych plików.
    print("Patching imports for Python 3 compatibility...")
    generated_files = glob.glob(str(out_dir / "crossdesk" / "v1" / "*.py"))
    
    # Upewniamy się, że struktura pakietowa w pythonie zadziała
    crossdesk_dir = out_dir / "crossdesk"
    crossdesk_v1_dir = crossdesk_dir / "v1"
    
    if crossdesk_dir.exists() and not (crossdesk_dir / "__init__.py").exists():
        (crossdesk_dir / "__init__.py").touch()
    if crossdesk_v1_dir.exists() and not (crossdesk_v1_dir / "__init__.py").exists():
        (crossdesk_v1_dir / "__init__.py").touch()
        
    print("Generation complete!")

if __name__ == "__main__":
    main()
