# CrossDesk GUI (mock)

Visual mock of the CrossDesk management console — Rust + Qt 6 (QML) via [CXX-Qt](https://github.com/KDAB/cxx-qt).

> **Status**: Pure UI mock. No connection to `host/`, `guest/`, or `proto/`. Buttons trigger fake state transitions only.

First iteration ships a single screen: **Install Wizard** for a new Windows VM (3 steps + simulated installation progress).

## Requirements

- macOS (Apple Silicon or Intel) or Linux
- Rust stable (edition 2021)
- Qt 6.5+ (6.7 recommended)
- CMake 3.24+

## macOS setup

```sh
brew install qt cmake
export CMAKE_PREFIX_PATH="$(brew --prefix qt)"
# persist for future shells:
echo 'export CMAKE_PREFIX_PATH="$(brew --prefix qt)"' >> ~/.zshrc
```

## Linux setup (Debian/Ubuntu)

```sh
sudo apt install qt6-base-dev qt6-declarative-dev qml6-module-qtquick \
                 qml6-module-qtquick-controls qml6-module-qtquick-dialogs \
                 qt6-tools-dev qt6-tools-dev-tools cmake
```

## Build & run

```sh
cd gui
cargo run -p crossdesk-gui
```

First clean build takes 2–5 min (CXX-Qt code generation + Qt binding compile).

## Workspace layout

```
gui/
├── Cargo.toml                  # workspace
└── crates/
    └── crossdesk-gui/
        ├── build.rs            # CxxQtBuilder + qrc registration
        ├── src/
        │   ├── main.rs
        │   ├── wizard/         # WizardState QObject + fake progress engine
        │   └── i18n/           # QTranslator helpers
        ├── qml/                # QML views (Main + wizard/*)
        ├── qml.qrc             # Qt resource bundle
        └── i18n/               # crossdesk_{en,pl}.ts (Qt Linguist)
```

## i18n workflow

```sh
# Update source strings from QML + Rust into .ts files:
lupdate crates/crossdesk-gui/qml crates/crossdesk-gui/src \
        -ts crates/crossdesk-gui/i18n/crossdesk_en.ts \
            crates/crossdesk-gui/i18n/crossdesk_pl.ts

# Compile to .qm (binary) for runtime loading:
lrelease crates/crossdesk-gui/i18n/crossdesk_en.ts \
         crates/crossdesk-gui/i18n/crossdesk_pl.ts
```

The `.qm` files are picked up by `qml.qrc` and embedded into the binary.
