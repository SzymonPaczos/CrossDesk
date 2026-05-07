//! Transport split per DEC-0005. The `tower::Service<Uri>` shape is the
//! abstraction — both implementations satisfy it, callers parameterise
//! over it.

pub mod real;

#[cfg(any(test, feature = "mock"))]
pub mod mock;
