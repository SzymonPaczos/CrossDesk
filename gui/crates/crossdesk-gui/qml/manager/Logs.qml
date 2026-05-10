import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: logs
    property string paneId: "logs"

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
                text: qsTr("Logs")
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: palette.text
                font.letterSpacing: -0.3
            }
        }

        // ── Toolbar ───────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 46
            color: palette.window

            Rectangle {
                anchors.bottom: parent.bottom
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

                ComboBox {
                    model: ["all", "info", "warning", "error", "critical"]
                    font.pixelSize: 12
                    Layout.preferredWidth: 100
                }
                ComboBox {
                    model: ["all", "heartbeat", "control", "filesystem", "lifecycle", "rail"]
                    font.pixelSize: 12
                    Layout.preferredWidth: 120
                }
                TextField {
                    placeholderText: qsTr("Search…")
                    font.pixelSize: 12
                    Layout.fillWidth: true
                }
                CheckBox {
                    text: qsTr("Follow")
                    checked: true
                    font.pixelSize: 12
                }
            }
        }

        // ── Log view (dark terminal panel) ────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Layout.topMargin: 16
            Layout.bottomMargin: 16
            color: "#0e0e0e"
            radius: 6
            border.color: palette.mid
            border.width: 1
            clip: true

            ScrollView {
                anchors.fill: parent
                anchors.margins: 0
                ScrollBar.vertical.policy: ScrollBar.AlwaysOn
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ListView {
                    id: logListView
                    model: mgr.log_lines
                    spacing: 0
                    leftMargin: 14
                    topMargin: 12
                    bottomMargin: 12

                    delegate: Item {
                        required property string modelData
                        required property int index
                        width: logListView.width - 28
                        height: logLabel.implicitHeight + 2

                        // Color-code by level prefix in the line
                        readonly property color lineColor: {
                            var l = modelData.toLowerCase();
                            if (l.indexOf("error") !== -1 || l.indexOf("critical") !== -1)
                                return "#ff8a8f";
                            if (l.indexOf("warn") !== -1)
                                return "#ffd95a";
                            if (l.indexOf("debug") !== -1)
                                return "#888888";
                            return "#e6e6e6";
                        }

                        Label {
                            id: logLabel
                            width: parent.width
                            text: modelData
                            font.family: "monospace"
                            font.pixelSize: 11
                            color: parent.lineColor
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }
    }
}
