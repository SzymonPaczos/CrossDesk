fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure().compile(
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
