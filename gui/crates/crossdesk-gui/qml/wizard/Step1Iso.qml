import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Qt.labs.folderlistmodel
import QtCore

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

    // Scans ~/Downloads for *.iso files — no Rust changes needed.
    FolderListModel {
        id: downloadsModel
        folder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        nameFilters: ["*.iso", "*.ISO"]
        showDirs: false
        sortField: FolderListModel.Size
        sortReversed: true
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
                        text: qsTr("Drop a .iso file or pick from downloads detected on your system.")
                        color: palette.placeholderText
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // ── Drop zone ─────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    height: 130
                    radius: 8
                    color: wizard.iso_path.length > 0
                           ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.06)
                           : palette.base
                    border.color: wizard.iso_path.length > 0 ? palette.highlight : palette.mid
                    border.width: wizard.iso_path.length > 0 ? 1 : 2

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: wizard.iso_path.length === 0

                        Label {
                            text: qsTr("Drag a Windows ISO here")
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: palette.text
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Label {
                            text: qsTr("or click to browse · Windows 10 / 11 supported")
                            font.pixelSize: 12
                            color: palette.placeholderText
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Button {
                            text: qsTr("Browse files…")
                            Layout.alignment: Qt.AlignHCenter
                            onClicked: fileDialog.open()
                        }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        visible: wizard.iso_path.length > 0

                        Label {
                            text: qsTr("ISO selected")
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: palette.highlight
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Label {
                            text: wizard.iso_path.replace("file://", "")
                            font.family: "monospace"
                            font.pixelSize: 11
                            color: palette.text
                            Layout.alignment: Qt.AlignHCenter
                            wrapMode: Text.WrapAnywhere
                            horizontalAlignment: Text.AlignHCenter
                            Layout.preferredWidth: 380
                        }
                        Button {
                            text: qsTr("Change…")
                            Layout.alignment: Qt.AlignHCenter
                            onClicked: fileDialog.open()
                            font.pixelSize: 11
                        }
                    }
                }

                // ── Detected ISOs in ~/Downloads ───────────────
                ColumnLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 6
                    visible: downloadsModel.count > 0

                    Label {
                        text: qsTr("DETECTED ON THIS SYSTEM")
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: palette.placeholderText
                        font.letterSpacing: 0.5
                        topPadding: 4
                    }

                    Repeater {
                        model: downloadsModel

                        delegate: Rectangle {
                            required property string fileName
                            required property string filePath
                            required property int fileSize

                            property string fileUrl: "file://" + filePath
                            property bool isSelected: wizard.iso_path === fileUrl
                            property string sizeLabel: {
                                var gib = fileSize / (1024 * 1024 * 1024);
                                return gib >= 0.1 ? gib.toFixed(1) + " GiB" : "< 0.1 GiB";
                            }
                            // Strip _x64/_x86 suffixes and underscores for a cleaner label.
                            property string displayName: {
                                var n = fileName.replace(/\.iso$/i, "")
                                                .replace(/_x64|_x86|_ARM64/gi, "")
                                                .replace(/_/g, " ")
                                                .replace(/\s+/g, " ").trim();
                                return n;
                            }

                            Layout.fillWidth: true
                            height: 56
                            radius: 6
                            color: isSelected
                                   ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.08)
                                   : palette.base
                            border.color: isSelected ? palette.highlight : palette.mid
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 10

                                RadioButton {
                                    checked: isSelected
                                    onClicked: wizard.iso_path = fileUrl
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Label {
                                        text: displayName
                                        font.pixelSize: 13
                                        font.weight: Font.Medium
                                        color: palette.text
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        text: filePath
                                        font.pixelSize: 11
                                        font.family: "monospace"
                                        color: palette.placeholderText
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }

                                Label {
                                    text: sizeLabel
                                    font.pixelSize: 12
                                    color: palette.placeholderText
                                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: wizard.iso_path = fileUrl
                            }
                        }
                    }
                }

                // Empty-state when Downloads has no ISOs and none selected
                Label {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    visible: downloadsModel.count === 0 && wizard.iso_path.length === 0
                    text: qsTr("No ISO files found in Downloads — use Browse above.")
                    font.pixelSize: 12
                    color: palette.placeholderText
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Item { height: 8 }
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
                    text: qsTr("Cancel")
                    onClicked: step.cancel()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Continue")
                    highlighted: true
                    enabled: wizard.iso_path.length > 0
                    onClicked: step.next()
                }
            }
        }
    }
}
