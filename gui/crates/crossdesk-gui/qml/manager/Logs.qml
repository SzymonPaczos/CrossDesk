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
        anchors.margins: 16
        spacing: 8

        RowLayout {
            spacing: 8
            Layout.fillWidth: true
            Label { text: qsTr("Filter:") }
            ComboBox {
                model: ["all", "info", "warning", "error", "critical"]
            }
            ComboBox {
                model: ["all", "heartbeat", "control", "filesystem", "lifecycle", "rail"]
            }
            TextField {
                placeholderText: qsTr("Search…")
                Layout.fillWidth: true
            }
            CheckBox {
                text: qsTr("Follow")
                checked: true
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                model: mgr.log_lines
                delegate: Label {
                    text: modelData
                    font.family: "monospace"
                    font.pixelSize: 11
                }
            }
        }
    }
}
