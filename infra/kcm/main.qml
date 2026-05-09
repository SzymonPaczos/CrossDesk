// KCM (KDE System Settings module) for CrossDesk.
//
// Plasma 6 loads this QML directly into the System Settings host
// process. The KCModule wrapper (in C++) wires the kcm.* properties.
// We re-use the same Manager UI surface so users don't have a
// different look-and-feel between System Settings and the standalone
// Manager binary.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: root
    title: i18n("Windows Apps")

    Kirigami.FormLayout {
        Kirigami.Heading {
            text: i18n("CrossDesk Manager")
            level: 2
            Layout.fillWidth: true
        }

        Label {
            text: i18n("Run Windows applications as native Linux windows. The full Manager UI is available as a separate window:")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Button {
            text: i18n("Open Manager")
            onClicked: Qt.openUrlExternally("application://crossdesk-manager.desktop")
        }

        Kirigami.Separator { Layout.fillWidth: true }

        Kirigami.Heading {
            text: i18n("VM status")
            level: 3
            Layout.fillWidth: true
        }

        // The KCM ships a slim status overview rather than embedding
        // the full Manager. Users who want the dashboard, logs, etc.
        // launch the standalone window via the button above.
        Label { text: i18n("Status: querying…") }
        Label { text: i18n("Heartbeat RTT: —") }
        Label { text: i18n("Active mounts: —") }

        Kirigami.Separator { Layout.fillWidth: true }

        Kirigami.Heading {
            text: i18n("Settings")
            level: 3
            Layout.fillWidth: true
        }

        CheckBox { text: i18n("Use KWallet for credentials"); checked: true }
        CheckBox { text: i18n("Auto-suspend VM when idle"); checked: false }
        CheckBox { text: i18n("Anonymous telemetry"); checked: false }
    }
}
