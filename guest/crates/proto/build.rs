fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Force tonic-build to use the vendored protoc so the crate builds
    // without a system-installed protoc, including inside cross-rs
    // images.
    std::env::set_var("PROTOC", protoc_bin_vendored::protoc_bin_path()?);

    tonic_build::configure().compile_protos(
        &[
            "../../../proto/crossdesk/v1/common.proto",
            "../../../proto/crossdesk/v1/control.proto",
            "../../../proto/crossdesk/v1/filesystem.proto",
            "../../../proto/crossdesk/v1/heartbeat.proto",
        ],
        &["../../../proto"],
    )?;
    Ok(())
}
