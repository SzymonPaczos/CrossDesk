import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: storage
    property string paneId: "storage"

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

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                spacing: 1
                Label {
                    text: qsTr("Storage")
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                    color: palette.text
                    font.letterSpacing: -0.3
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width

            ColumnLayout {
                width: storage.width
                Layout.margins: 24
                spacing: 16

                // Active mounts card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: activeMountsHeader.height + activeMountsBody.implicitHeight + 28

                    Rectangle {
                        id: activeMountsHeader
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
                                text: qsTr("Active JIT mounts (%1)").arg(mgr.active_mounts.length)
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                            Item { Layout.fillWidth: true }
                            // Live indicator
                            Rectangle {
                                visible: mgr.active_mounts.length > 0
                                width: liveBadge.implicitWidth + 18
                                height: 20
                                radius: 10
                                color: Qt.rgba(0.18, 0.76, 0.49, 0.15)

                                RowLayout {
                                    id: liveBadge
                                    anchors.centerIn: parent
                                    spacing: 5

                                    Rectangle {
                                        width: 6; height: 6; radius: 3
                                        color: "#4caf50"
                                    }
                                    Label {
                                        text: mgr.active_mounts.length + qsTr(" active")
                                        font.pixelSize: 10
                                        font.weight: Font.Medium
                                        color: "#4caf50"
                                    }
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        id: activeMountsBody
                        anchors.top: activeMountsHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 4

                        Label {
                            visible: mgr.active_mounts.length === 0
                            text: qsTr("No active mounts.\nMounts appear here when you open a file in a Windows app and disappear when the app closes.")
                            color: palette.placeholderText
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            font.pixelSize: 12
                        }

                        Repeater {
                            model: mgr.active_mounts
                            delegate: Label {
                                text: modelData
                                font.family: "monospace"
                                font.pixelSize: 11
                                color: palette.text
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                // Mount history card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: histHeader.height + histBody.implicitHeight + 28

                    Rectangle {
                        id: histHeader
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
                                text: qsTr("Recent mount history")
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                        }
                    }

                    ColumnLayout {
                        id: histBody
                        anchors.top: histHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 4

                        Label {
                            visible: mgr.recent_mounts.length === 0
                            text: qsTr("History empties when you uninstall.")
                            color: palette.placeholderText
                            font.pixelSize: 12
                        }

                        Repeater {
                            model: mgr.recent_mounts
                            delegate: Item {
                                Layout.fillWidth: true
                                height: 28

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.bottomMargin: -1
                                    color: "transparent"

                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        height: 1
                                        color: palette.mid
                                        opacity: 0.4
                                        visible: index < mgr.recent_mounts.length - 1
                                    }
                                }

                                Label {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData
                                    font.family: "monospace"
                                    font.pixelSize: 11
                                    color: palette.text
                                }
                            }
                        }
                    }
                }

                Item { height: 8 }
            }
        }
    }
}
