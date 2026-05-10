import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: step
    property var wizard
    signal next()
    signal cancel()

    FileDialog {
        id: fileDialog
        title: qsTr("Select Windows ISO image")
        nameFilters: [qsTr("ISO images (*.iso)"), qsTr("All files (*)")]
        onAccepted: wizard.iso_path = selectedFile.toString()
    }

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
                anchors.leftMargin: 32
                anchors.rightMargin: 32
                spacing: 20

                Item { height: 4 }

                ColumnLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 4
                    Label {
                        text: qsTr("Step 1 of 3 — Installation media")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        font.letterSpacing: -0.3
                    }
                    Label {
                        text: qsTr("Choose the Windows installation ISO. The image will be attached as a virtual CD-ROM during the autounattend bootstrap.")
                        color: palette.placeholderText
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Drop zone
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    height: 140
                    radius: 8
                    color: wizard.iso_path.length > 0
                           ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.06)
                           : palette.base
                    border.color: wizard.iso_path.length > 0 ? palette.highlight : palette.mid
                    border.width: wizard.iso_path.length > 0 ? 1 : 2

                    // Dashed border effect (simulated via inner Rectangle with no fill + dash stroke using canvas)
                    // Simplified: solid border when empty, highlighted when filled.

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: wizard.iso_path.length === 0

                        Label {
                            text: qsTr("Drop ISO here or click Browse")
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: palette.text
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Label {
                            text: qsTr("Windows 10 / 11 installation media")
                            font.pixelSize: 12
                            color: palette.placeholderText
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Button {
                            text: qsTr("Browse…")
                            Layout.alignment: Qt.AlignHCenter
                            onClicked: fileDialog.open()
                        }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: wizard.iso_path.length > 0

                        Label {
                            text: qsTr("ISO selected")
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: palette.highlight
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Label {
                            text: wizard.iso_path
                            font.family: "monospace"
                            font.pixelSize: 11
                            color: palette.text
                            Layout.alignment: Qt.AlignHCenter
                            wrapMode: Text.WrapAnywhere
                            horizontalAlignment: Text.AlignHCenter
                        }
                        Button {
                            text: qsTr("Change…")
                            Layout.alignment: Qt.AlignHCenter
                            onClicked: fileDialog.open()
                            font.pixelSize: 11
                        }
                    }
                }

                // Manual path field
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 8

                    TextField {
                        id: pathField
                        text: wizard.iso_path
                        placeholderText: qsTr("No ISO selected")
                        readOnly: true
                        Layout.fillWidth: true
                        font.pixelSize: 12
                        font.family: "monospace"
                    }

                    Button {
                        text: qsTr("Browse…")
                        onClicked: fileDialog.open()
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
                    onClicked: step.cancel()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Next")
                    highlighted: true
                    enabled: wizard.iso_path.length > 0
                    onClicked: step.next()
                }
            }
        }
    }
}
