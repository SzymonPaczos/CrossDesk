import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: step
    property var wizard
    signal back()
    signal install()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Step body ─────────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width

            ColumnLayout {
                width: step.width
                spacing: 20

                Item { height: 4 }

                ColumnLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 4

                    Label {
                        text: qsTr("Step 2 of 2 — Review & Install")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        font.letterSpacing: -0.3
                    }
                    Label {
                        text: qsTr("CrossDesk detected the following settings from your host system. No manual configuration needed.")
                        color: palette.placeholderText
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Summary card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: summaryGrid.implicitHeight + 32

                    GridLayout {
                        id: summaryGrid
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 16
                        columns: 2
                        rowSpacing: 14
                        columnSpacing: 16

                        Label {
                            text: qsTr("ISO")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: palette.placeholderText
                            Layout.preferredWidth: 100
                        }
                        Label {
                            text: {
                                var p = wizard.iso_path;
                                var sep = p.lastIndexOf("/");
                                return sep >= 0 ? p.substring(sep + 1) : p;
                            }
                            font.pixelSize: 12
                            color: palette.text
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.columnSpan: 2
                            Layout.fillWidth: true
                            height: 1
                            color: palette.mid
                        }

                        Label {
                            text: qsTr("Timezone")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: palette.placeholderText
                        }
                        Label {
                            text: wizard.host_timezone
                            font.pixelSize: 12
                            color: palette.text
                        }

                        Label {
                            text: qsTr("Locale")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: palette.placeholderText
                        }
                        Label {
                            text: wizard.host_locale
                            font.pixelSize: 12
                            color: palette.text
                        }

                        Rectangle {
                            Layout.columnSpan: 2
                            Layout.fillWidth: true
                            height: 1
                            color: palette.mid
                        }

                        Label {
                            text: qsTr("RAM")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: palette.placeholderText
                        }
                        Label {
                            text: qsTr("%1 GB (50% of host RAM)").arg(wizard.host_ram_gb)
                            font.pixelSize: 12
                            color: palette.text
                        }

                        Label {
                            text: qsTr("vCPU")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: palette.placeholderText
                        }
                        Label {
                            text: qsTr("%1 cores (half of host cores)").arg(wizard.host_vcpu)
                            font.pixelSize: 12
                            color: palette.text
                        }

                        Label {
                            text: qsTr("Disk")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: palette.placeholderText
                        }
                        Label {
                            text: qsTr("%1 GB (thin-provisioned)").arg(wizard.disk_gb)
                            font.pixelSize: 12
                            color: palette.text
                        }
                    }
                }

                // Info note
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    color: Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.07)
                    border.color: Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.25)
                    border.width: 1
                    radius: 6
                    implicitHeight: noteLabel.implicitHeight + 20

                    Label {
                        id: noteLabel
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 12
                        text: qsTr("Memory and CPU are shared with the host and can be adjusted later in Settings. The disk image grows on demand — %1 GB is the maximum cap.").arg(wizard.disk_gb)
                        font.pixelSize: 12
                        color: palette.text
                        wrapMode: Text.WordWrap
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ── Sticky footer ─────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 52
            color: palette.alternateBase

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: palette.mid
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: 8

                Button {
                    text: qsTr("Back")
                    onClicked: step.back()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Install")
                    highlighted: true
                    onClicked: step.install()
                }
            }
        }
    }
}
