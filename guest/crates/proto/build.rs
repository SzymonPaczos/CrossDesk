use std::path::{Path, PathBuf};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Force tonic-build to use the vendored protoc so the crate builds
    // without a system-installed protoc, including inside cross-rs
    // images.
    std::env::set_var("PROTOC", protoc_bin_vendored::protoc_bin_path()?);

    let proto_dir = resolve_proto_dir();
    println!("cargo:rerun-if-env-changed=CROSSDESK_PROTO_DIR");
    println!("cargo:rerun-if-changed={}", proto_dir.display());

    let files: Vec<PathBuf> = [
        "common.proto",
        "control.proto",
        "filesystem.proto",
        "heartbeat.proto",
    ]
    .iter()
    .map(|name| proto_dir.join("crossdesk/v1").join(name))
    .collect();

    tonic_build::configure().compile_protos(&files, &[proto_dir])?;
    Ok(())
}

/// Resolves where the ``.proto`` IDL tree lives on disk.
///
/// Resolution order (first existing wins):
///
/// 1. ``CROSSDESK_PROTO_DIR`` env var — explicit override for
///    cross-rs / CI runs.
/// 2. ``guest/proto-vendored/`` (relative to ``guest/crates/proto/``)
///    — populated by ``scripts/cross-build-agent.sh`` before the
///    container build, so cross-rs sees the IDL inside the workspace
///    mount.
/// 3. ``../../../proto`` — the canonical in-repo path, used by
///    native ``cargo build`` and ``cargo check --target …`` flows.
fn resolve_proto_dir() -> PathBuf {
    if let Ok(p) = std::env::var("CROSSDESK_PROTO_DIR") {
        let path = PathBuf::from(p);
        if path.is_dir() {
            return path;
        }
    }
    let vendored = Path::new("../../proto-vendored");
    if vendored.is_dir() {
        return vendored.to_path_buf();
    }
    PathBuf::from("../../../proto")
}
