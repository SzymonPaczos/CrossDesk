import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: diagnose
    property string paneId: "diagnose"

    ManagerState { id: mgr }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Pane header ───────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 52
            color: palette.alternateBase

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: palette.mid
            }

            Label {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 24
                text: qsTr("Diagnose")
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: palette.text
                font.letterSpacing: -0.3
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width

            ColumnLayout {
                width: diagnose.width
                Layout.margins: 24
                spacing: 16

                // Pre-flight checks card (flush padded — no inner margins, list fills)
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    clip: true
                    implicitHeight: pfHeader.height + pfList.implicitHeight

                    Rectangle {
                        id: pfHeader
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 38
                        color: "transparent"
                        radius: 6

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            color: palette.mid
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14

                            Label {
                                text: qsTr("Pre-flight check")
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                            Item { Layout.fillWidth: true }
                            Button {
                                text: qsTr("Re-run")
                                onClicked: mgr.run_diagnostics()
                                font.pixelSize: 11
                            }
                            Button {
                                text: qsTr("Export bundle")
                                font.pixelSize: 11
                            }
                        }
                    }

                    ColumnLayout {
                        id: pfList
                        anchors.top: pfHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        spacing: 0

                        Repeater {
                            model: mgr.diagnostics
                            delegate: Item {
                                Layout.fillWidth: true
                                height: checkRow.implicitHeight + 16

                                required property var modelData
                                required property int index

                                readonly property var parts: modelData.split("|")
                                readonly property string status: parts[0]
                                readonly property string checkName: parts[1]
                                readonly property string message: parts.length > 2 ? parts[2] : ""

                                // Row background — tinted for warn/fail
                                Rectangle {
                                    anchors.fill: parent
                                    color: status === "warn"
                                           ? Qt.rgba(1.0, 0.6, 0.0, 0.06)
                                           : status === "fail"
                                             ? Qt.rgba(0.96, 0.26, 0.21, 0.06)
                                             : "transparent"
                                }

                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    height: 1
                                    color: palette.mid
                                    opacity: 0.5
                                    visible: index < mgr.diagnostics.length - 1
                                }

                                RowLayout {
                                    id: checkRow
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    spacing: 10

                                    // Status icon (colored circle with symbol)
                                    Rectangle {
                                        width: 16; height: 16; radius: 8
                                        color: status === "ok"   ? "#4caf50"
                                             : status === "warn" ? "#ff9800"
                                             : status === "fail" ? "#f44336"
                                             :                     "#9e9e9e"

                                        Label {
                                            anchors.centerIn: parent
                                            text: status === "ok" ? "✓"
                                                : status === "warn" ? "!"
                                                : "✗"
                                            font.pixelSize: 10
                                            font.weight: Font.Bold
                                            color: "white"
                                        }
                                    }

                                    Label {
                                        text: checkName
                                        font.family: "monospace"
                                        font.pixelSize: 12
                                        font.weight: Font.Medium
                                        Layout.preferredWidth: 160
                                    }

                                    Label {
                                        text: message
                                        color: palette.placeholderText
                                        font.pixelSize: 12
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        // Empty state
                        Label {
                            visible: mgr.diagnostics.length === 0
                            Layout.fillWidth: true
                            Layout.margins: 14
                            text: qsTr("No diagnostics data. Run a check to see results.")
                            color: palette.placeholderText
                            font.pixelSize: 12
                        }
                    }
                }

                Item { height: 8 }
            }
        }
    }

    function glyphFor(status) {
        switch (status) {
            case "ok":   return "✓";
            case "warn": return "!";
            case "fail": return "✗";
        }
        return "?";
    }

    function colorFor(status) {
        switch (status) {
            case "ok":   return "#4caf50";
            case "warn": return "#ff9800";
            case "fail": return "#f44336";
        }
        return palette.placeholderText;
    }
}
