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

    // Scan is considered "done" once the model has reported at least one
    // count change OR the guard timer fires — whichever comes first.
    // This prevents showing the spinner forever when Downloads has no ISOs.
    property bool scanReady: false

    FileDialog {
        id: fileDialog
        title: qsTr("Select Windows ISO image")
        nameFilters: [qsTr("ISO images (*.iso)"), qsTr("All files (*)")]
        onAccepted: wizard.iso_path = selectedFile.toString()
    }

    FolderListModel {
        id: downloadsModel
        folder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        nameFilters: ["*.iso", "*.ISO"]
        showDirs: false
        sortField: FolderListModel.Size
        sortReversed: true
        onCountChanged: {
            // First count notification → scan has returned at least one result.
            if (!scanReady) {
                scanTimer.stop()
                scanReady = true
            }
        }
    }

    // Fallback: mark ready after 700 ms even if Downloads is empty.
    Timer {
        id: scanTimer
        interval: 700
        running: true
        repeat: false
        onTriggered: scanReady = true
    }

    // Only show ISOs that look like Windows media; excludes Linux distros.
    function isWindowsIso(name) {
        var n = name.toLowerCase()
        return n.indexOf("win")       !== -1 ||
               n.indexOf("msdn")      !== -1 ||
               n.indexOf("ltsc")      !== -1 ||
               n.indexOf("microsoft") !== -1
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

                // ── Detected Windows ISOs ──────────────────────
                ColumnLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 6

                    // ── Spinner while scan runs ────────────────
                    RowLayout {
                        spacing: 10
                        visible: !scanReady

                        BusyIndicator {
                            running: !scanReady
                            implicitWidth: 22
                            implicitHeight: 22
                        }
                        Label {
                            text: qsTr("Scanning Downloads…")
                            font.pixelSize: 12
                            color: palette.placeholderText
                        }
                    }

                    // ── Section header (shown once scan is done and there are results) ──
                    Label {
                        visible: scanReady && downloadsModel.count > 0
                        text: qsTr("DETECTED ON THIS SYSTEM")
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: palette.placeholderText
                        font.letterSpacing: 0.5
                        topPadding: 4

                        Behavior on opacity { NumberAnimation { duration: 150 } }
                        opacity: visible ? 1 : 0
                    }

                    // ── ISO cards ─────────────────────────────
                    Repeater {
                        model: scanReady ? downloadsModel : null

                        delegate: Item {
                            required property string fileName
                            required property string filePath
                            required property int     fileSize
                            required property int     index

                            property bool isWin: isWindowsIso(fileName)
                            property string fileUrl: "file://" + filePath
                            property bool isSelected: wizard.iso_path === fileUrl
                            property string sizeLabel: {
                                var gib = fileSize / (1024 * 1024 * 1024)
                                return gib >= 0.1 ? gib.toFixed(1) + " GiB" : "< 0.1 GiB"
                            }
                            property string displayName: {
                                var n = fileName.replace(/\.iso$/i, "")
                                                .replace(/_(x64|x86|ARM64|amd64)/gi, "")
                                                .replace(/_/g, " ")
                                                .trim()
                                return n
                            }

                            Layout.fillWidth: true
                            // Non-Windows ISOs collapse to zero height — no gap.
                            height: isWin ? card.height : 0
                            clip: true
                            visible: isWin

                            Rectangle {
                                id: card
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: 60
                                radius: 6
                                color: isSelected
                                       ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.08)
                                       : palette.base
                                border.color: isSelected ? palette.highlight : palette.mid
                                border.width: 1
                                opacity: 0

                                // Staggered cascade appearance — each card fades in
                                // with a delay proportional to its position.
                                SequentialAnimation {
                                    running: isWin
                                    PauseAnimation { duration: Math.min(index * 70, 350) }
                                    NumberAnimation {
                                        target: card
                                        property: "opacity"
                                        to: 1
                                        duration: 220
                                        easing.type: Easing.OutQuad
                                    }
                                }

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

                    // Empty state: scan done, no Windows ISOs found.
                    Label {
                        visible: scanReady && downloadsModel.count === 0 && wizard.iso_path.length === 0
                        text: qsTr("No Windows ISO files found in Downloads — use Browse above.")
                        font.pixelSize: 12
                        color: palette.placeholderText
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        topPadding: 4
                    }
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
