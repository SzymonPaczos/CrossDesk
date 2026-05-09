import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: about
    property string paneId: "about"

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: about.width - 32
            spacing: 12

            Label {
                text: "CrossDesk Manager"
                font.bold: true
                font.pixelSize: 24
            }
            Label {
                text: qsTr("Version 0.1.0 (pre-release)")
                color: palette.placeholderText
            }
            Label {
                text: qsTr("Run Windows applications as native Wayland or X11 windows.")
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Label {
                textFormat: Text.RichText
                onLinkActivated: (link) => Qt.openUrlExternally(link)
                text: '<a href="https://github.com/SzymonPaczos/CrossDesk">GitHub</a> · ' +
                      '<a href="https://github.com/SzymonPaczos/CrossDesk/blob/main/docs/GOALS.md">Vision</a> · ' +
                      '<a href="https://github.com/SzymonPaczos/CrossDesk/blob/main/docs/THREAT_MODEL.md">Threat model</a>'
            }
            Label {
                text: qsTr("License: GPL-3.0-or-later")
                color: palette.placeholderText
            }
            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Label {
                        text: qsTr("Phase 4 SPOF")
                        font.bold: true
                    }
                    Label {
                        // Easter egg: per ROADMAP.md
                        text: "kolejność i idempotencja eventów (CREATED przed FOCUS_GAINED, brak zgubionego DESTROYED) — rozjazd stanu HWND↔Linux window = ghost windows lub orphaned process"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        color: palette.placeholderText
                    }
                }
            }
        }
    }
}
