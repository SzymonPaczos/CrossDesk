import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Qt.labs.folderlistmodel
import QtCore

Item {
    id: step
    property var wizard
    signal install()
    signal cancel()

    property bool scanReady: false

    readonly property bool isDownloadMode: wizard.iso_source === "download"
    readonly property bool canInstall:
        isDownloadMode || wizard.iso_path.length > 0

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
        onCountChanged: { if (!scanReady) { scanTimer.stop(); scanReady = true } }
    }

    Timer {
        id: scanTimer; interval: 700; running: true; repeat: false
        onTriggered: scanReady = true
    }

    function isWindowsIso(name) {
        var n = name.toLowerCase()
        return n.indexOf("win") !== -1 || n.indexOf("msdn") !== -1 ||
               n.indexOf("ltsc") !== -1 || n.indexOf("microsoft") !== -1
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
                        text: qsTr("Install Windows")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        font.letterSpacing: -0.3
                    }
                    Label {
                        text: qsTr("Download Windows 11 Pro automatically, or provide your own ISO.")
                        color: palette.placeholderText
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // ── Source mode toggle ─────────────────────────
                RowLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 8

                    // Download card
                    Rectangle {
                        Layout.fillWidth: true
                        height: 72
                        radius: 6
                        color: isDownloadMode
                               ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.08)
                               : palette.base
                        border.color: isDownloadMode ? palette.highlight : palette.mid
                        border.width: isDownloadMode ? 2 : 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 10

                            RadioButton {
                                checked: isDownloadMode
                                onClicked: wizard.iso_source = "download"
                            }
                            ColumnLayout {
                                spacing: 2
                                Label {
                                    text: qsTr("Download from Microsoft")
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: palette.text
                                }
                                Label {
                                    text: qsTr("~5 GB · free · official source")
                                    font.pixelSize: 11
                                    color: palette.placeholderText
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: wizard.iso_source = "download"
                        }
                    }

                    // Browse card
                    Rectangle {
                        Layout.fillWidth: true
                        height: 72
                        radius: 6
                        color: !isDownloadMode
                               ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.08)
                               : palette.base
                        border.color: !isDownloadMode ? palette.highlight : palette.mid
                        border.width: !isDownloadMode ? 2 : 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 10

                            RadioButton {
                                checked: !isDownloadMode
                                onClicked: wizard.iso_source = "browse"
                            }
                            ColumnLayout {
                                spacing: 2
                                Label {
                                    text: qsTr("I already have an ISO")
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: palette.text
                                }
                                Label {
                                    text: qsTr("Browse or detect from Downloads")
                                    font.pixelSize: 11
                                    color: palette.placeholderText
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: wizard.iso_source = "browse"
                        }
                    }
                }

                // ── Download mode ──────────────────────────────
                Rectangle {
                    visible: isDownloadMode
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    Layout.fillWidth: true
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: dlCol.implicitHeight + 32

                    ColumnLayout {
                        id: dlCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 16
                        spacing: 6

                        Label {
                            text: qsTr("Windows 11 Pro · %1").arg(wizard.download_language)
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: palette.text
                        }
                        Label {
                            text: qsTr("~5 GB · downloaded automatically from Microsoft")
                            font.pixelSize: 12
                            color: palette.placeholderText
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                        Label {
                            text: qsTr("Cached in ~/.cache/crossdesk/iso/ — reused on reinstall.")
                            font.pixelSize: 11
                            color: palette.placeholderText
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                // ── Browse mode ────────────────────────────────
                ColumnLayout {
                    visible: !isDownloadMode
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 10

                    // Drop zone
                    Rectangle {
                        Layout.fillWidth: true
                        height: 110
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
                                font.pixelSize: 14; font.weight: Font.Medium
                                color: palette.text; Layout.alignment: Qt.AlignHCenter
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
                                font.pixelSize: 13; font.weight: Font.DemiBold
                                color: palette.highlight; Layout.alignment: Qt.AlignHCenter
                            }
                            Label {
                                text: wizard.iso_path.replace("file://", "")
                                font.family: "monospace"; font.pixelSize: 11
                                color: palette.text; Layout.alignment: Qt.AlignHCenter
                                wrapMode: Text.WrapAnywhere; horizontalAlignment: Text.AlignHCenter
                                Layout.preferredWidth: 380
                            }
                            Button {
                                text: qsTr("Change…"); font.pixelSize: 11
                                Layout.alignment: Qt.AlignHCenter
                                onClicked: fileDialog.open()
                            }
                        }
                    }

                    // Detected ISOs in Downloads
                    RowLayout {
                        spacing: 10; visible: !scanReady
                        BusyIndicator { running: !scanReady; implicitWidth: 22; implicitHeight: 22 }
                        Label {
                            text: qsTr("Scanning Downloads…"); font.pixelSize: 12
                            color: palette.placeholderText
                        }
                    }

                    Label {
                        visible: scanReady && downloadsModel.count > 0
                        text: qsTr("DETECTED ON THIS SYSTEM")
                        font.pixelSize: 11; font.weight: Font.DemiBold
                        color: palette.placeholderText; font.letterSpacing: 0.5; topPadding: 4
                    }

                    Repeater {
                        model: scanReady ? downloadsModel : null

                        delegate: Item {
                            required property string fileName
                            required property string filePath
                            required property int     fileSize
                            required property int     index

                            property bool   isWin:     isWindowsIso(fileName)
                            property string fileUrl:   "file://" + filePath
                            property bool   isSel:     wizard.iso_path === fileUrl
                            property string sizeLabel: {
                                var gib = fileSize / (1024 * 1024 * 1024)
                                return gib >= 0.1 ? gib.toFixed(1) + " GiB" : "< 0.1 GiB"
                            }
                            property string displayName: {
                                return fileName.replace(/\.iso$/i, "")
                                               .replace(/_(x64|x86|ARM64|amd64)/gi, "")
                                               .replace(/_/g, " ").trim()
                            }

                            Layout.fillWidth: true
                            height: isWin ? card.height : 0; clip: true; visible: isWin

                            Rectangle {
                                id: card
                                anchors.left: parent.left; anchors.right: parent.right
                                height: 60; radius: 6; opacity: 0
                                color: isSel ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.08) : palette.base
                                border.color: isSel ? palette.highlight : palette.mid; border.width: 1

                                SequentialAnimation {
                                    running: isWin
                                    PauseAnimation { duration: Math.min(index * 70, 350) }
                                    NumberAnimation { target: card; property: "opacity"; to: 1; duration: 220; easing.type: Easing.OutQuad }
                                }

                                RowLayout {
                                    anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 10
                                    RadioButton { checked: isSel; onClicked: wizard.iso_path = fileUrl }
                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 2
                                        Label { text: displayName; font.pixelSize: 13; font.weight: Font.Medium; color: palette.text; elide: Text.ElideRight; Layout.fillWidth: true }
                                        Label { text: filePath; font.pixelSize: 11; font.family: "monospace"; color: palette.placeholderText; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    }
                                    Label { text: sizeLabel; font.pixelSize: 12; color: palette.placeholderText }
                                }
                                MouseArea { anchors.fill: parent; onClicked: wizard.iso_path = fileUrl }
                            }
                        }
                    }

                    Label {
                        visible: scanReady && downloadsModel.count === 0 && wizard.iso_path.length === 0
                        text: qsTr("No Windows ISO files found in Downloads — use Browse above.")
                        font.pixelSize: 12; color: palette.placeholderText
                        wrapMode: Text.WordWrap; Layout.fillWidth: true; topPadding: 4
                    }
                }

                // ── Auto-detected VM parameters hint ──────────
                Label {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    text: qsTr("Your VM will use %1 GB RAM · %2 vCPU · 64 GB disk · %3")
                          .arg(wizard.host_ram_gb)
                          .arg(wizard.host_vcpu)
                          .arg(wizard.host_timezone)
                    font.pixelSize: 11
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
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                height: 1; color: palette.mid
            }

            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 24; anchors.rightMargin: 24; spacing: 8

                Button {
                    text: qsTr("Cancel")
                    onClicked: step.cancel()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Install")
                    highlighted: true
                    enabled: canInstall
                    onClicked: step.install()
                }
            }
        }
    }
}
