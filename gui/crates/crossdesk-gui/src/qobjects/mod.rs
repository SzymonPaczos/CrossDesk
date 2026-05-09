//! cxx-qt bridge modules collocated in one directory.
//!
//! cxx-qt-build requires every Rust file in a `QmlModule` to share a
//! single source directory (Qt bug QTBUG-93443). We collocate every
//! qobject here; logic that doesn't need a Qt bridge stays in its
//! topical module (`crate::wizard`, `crate::manager`).

pub mod manager;
pub mod wizard;
