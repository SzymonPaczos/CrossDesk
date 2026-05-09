import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: dashboard
    property string paneId: "dashboard"

    ManagerState { id: mgr }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: dashboard.width - 32
            spacing: 16

            // Status card
            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    RowLayout {
                        spacing: 12
                        Label {
                            text: severityDot(mgr.fsm_severity)
                            font.pixelSize: 18
                        }
                        Label {
                            text: mgr.fsm_state
                            font.bold: true
                            font.pixelSize: 18
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            text: qsTr("Uptime: %1").arg(mgr.uptime_label)
                            color: palette.placeholderText
                        }
                    }
                    Label {
                        text: qsTr("Heartbeat RTT: %1 ms").arg(mgr.ewma_rtt_ms)
                    }
                    Label {
                        text: qsTr("AuthContext rejections: %1").arg(mgr.auth_rejections)
                    }
                    Label {
                        text: qsTr("Active mounts: %1").arg(mgr.active_mounts.length)
                    }
                }
            }

            // Resources
            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    Label {
                        text: qsTr("Resources")
                        font.bold: true
                    }
                    RowLayout {
                        spacing: 8
                        Label { text: qsTr("CPU"); Layout.preferredWidth: 60 }
                        ProgressBar {
                            from: 0; to: 100; value: mgr.cpu_percent
                            Layout.fillWidth: true
                        }
                        Label { text: mgr.cpu_percent + " %"; Layout.preferredWidth: 50 }
                    }
                    RowLayout {
                        spacing: 8
                        Label { text: qsTr("RAM"); Layout.preferredWidth: 60 }
                        ProgressBar {
                            from: 0; to: 100; value: mgr.ram_percent
                            Layout.fillWidth: true
                        }
                        Label { text: mgr.ram_label; Layout.preferredWidth: 140 }
                    }
                }
            }

            // Recent activity
            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Label {
                        text: qsTr("Recent activity")
                        font.bold: true
                    }
                    Repeater {
                        model: mgr.recent_activity
                        delegate: Label {
                            text: modelData
                            font.family: "monospace"
                        }
                    }
                }
            }

            // Quick actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Button {
                    text: qsTr("Launch app...")
                    onClicked: dashboard.parent.parent.replace(
                        "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Apps.qml")
                }
                Button {
                    text: qsTr("Suspend VM")
                    onClicked: mgr.suspend()
                }
                Button {
                    text: qsTr("View logs")
                    onClicked: dashboard.parent.parent.replace(
                        "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Logs.qml")
                }
                Item { Layout.fillWidth: true }
            }
        }
    }

    function severityDot(sev) {
        switch (sev) {
            case "ok":       return "🟢";
            case "warn":     return "🟡";
            case "critical": return "🔴";
            default:         return "⚪";
        }
    }
}
