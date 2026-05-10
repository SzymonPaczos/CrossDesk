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
        contentWidth: width

        ColumnLayout {
            width: dashboard.width
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

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 24
                    spacing: 1
                    Label {
                        text: qsTr("Dashboard")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        font.letterSpacing: -0.3
                    }
                }
            }

            // ── Content ───────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: 24
                spacing: 16

                // Status card
                Rectangle {
                    Layout.fillWidth: true
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: statusHeader.height + statusBody.implicitHeight + 28

                    Rectangle {
                        id: statusHeader
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
                                text: qsTr("VM Status")
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: qsTr("Uptime: %1").arg(mgr.uptime_label)
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
                        }
                    }

                    RowLayout {
                        id: statusBody
                        anchors.top: statusHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 16

                        Rectangle {
                            implicitWidth: 14
                            implicitHeight: 14
                            radius: 7
                            color: severityColor(mgr.fsm_severity)
                            Layout.alignment: Qt.AlignVCenter
                        }

                        ColumnLayout {
                            spacing: 2
                            Label {
                                text: mgr.fsm_state
                                font.pixelSize: 15
                                font.weight: Font.Bold
                                font.family: "monospace"
                                color: palette.text
                                font.letterSpacing: 0.8
                            }
                            Label {
                                text: qsTr("Heartbeat RTT: %1 ms").arg(mgr.ewma_rtt_ms)
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
                        }

                        Item { Layout.fillWidth: true }

                        GridLayout {
                            columns: 2
                            rowSpacing: 8
                            columnSpacing: 28

                            Label {
                                text: qsTr("AuthCtx rejections")
                                font.pixelSize: 10
                                color: palette.placeholderText
                                font.capitalization: Font.AllUppercase
                                font.letterSpacing: 0.4
                            }
                            Label {
                                text: mgr.auth_rejections
                                font.pixelSize: 12
                                font.family: "monospace"
                            }

                            Label {
                                text: qsTr("Active mounts")
                                font.pixelSize: 10
                                color: palette.placeholderText
                                font.capitalization: Font.AllUppercase
                                font.letterSpacing: 0.4
                            }
                            Label {
                                text: mgr.active_mounts.length
                                font.pixelSize: 12
                                font.family: "monospace"
                            }
                        }
                    }
                }

                // Resources card
                Rectangle {
                    Layout.fillWidth: true
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: resourcesHeader.height + resourcesBody.implicitHeight + 28

                    Rectangle {
                        id: resourcesHeader
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

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            text: qsTr("Resources")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: resourcesBody
                        anchors.top: resourcesHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 14

                        // CPU bar
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    text: qsTr("CPU")
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    Layout.preferredWidth: 44
                                }
                                Item { Layout.fillWidth: true }
                                Label {
                                    text: mgr.cpu_percent + " %"
                                    font.pixelSize: 11
                                    font.family: "monospace"
                                    color: palette.placeholderText
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 6
                                radius: 3
                                color: palette.mid
                                Rectangle {
                                    width: parent.width * (mgr.cpu_percent / 100.0)
                                    height: parent.height
                                    radius: 3
                                    color: palette.highlight
                                }
                            }
                        }

                        // RAM bar
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    text: qsTr("RAM")
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    Layout.preferredWidth: 44
                                }
                                Item { Layout.fillWidth: true }
                                Label {
                                    text: mgr.ram_label
                                    font.pixelSize: 11
                                    font.family: "monospace"
                                    color: palette.placeholderText
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 6
                                radius: 3
                                color: palette.mid
                                Rectangle {
                                    width: parent.width * (mgr.ram_percent / 100.0)
                                    height: parent.height
                                    radius: 3
                                    color: palette.highlight
                                }
                            }
                        }
                    }
                }

                // Recent activity card
                Rectangle {
                    Layout.fillWidth: true
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: activityHeader.height + activityBody.implicitHeight + 28

                    Rectangle {
                        id: activityHeader
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

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            text: qsTr("Recent activity")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: activityBody
                        anchors.top: activityHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 4

                        Repeater {
                            model: mgr.recent_activity
                            delegate: Label {
                                text: modelData
                                font.family: "monospace"
                                font.pixelSize: 11
                                color: palette.text
                                Layout.fillWidth: true
                            }
                        }

                        Label {
                            visible: mgr.recent_activity.length === 0
                            text: qsTr("No recent activity.")
                            color: palette.placeholderText
                            font.pixelSize: 12
                        }
                    }
                }

                // Quick actions row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        text: qsTr("Launch app…")
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

                Item { height: 8 }
            }
        }
    }

    function severityColor(sev) {
        switch (sev) {
            case "ok":       return "#4caf50";
            case "warn":     return "#ff9800";
            case "critical": return "#f44336";
            default:         return "#9e9e9e";
        }
    }
}
