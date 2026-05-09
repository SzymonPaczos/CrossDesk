import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: storage
    property string paneId: "storage"

    ManagerState { id: mgr }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: storage.width - 32
            spacing: 16

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    Label {
                        text: qsTr("Active JIT mounts (%1)").arg(mgr.active_mounts.length)
                        font.bold: true
                    }
                    Label {
                        visible: mgr.active_mounts.length === 0
                        text: qsTr("No active mounts.\nMounts appear here when you open a file in a Windows app and disappear when the app closes.")
                        color: palette.placeholderText
                        wrapMode: Text.WordWrap
                    }
                    Repeater {
                        model: mgr.active_mounts
                        delegate: Label {
                            text: modelData
                            font.family: "monospace"
                        }
                    }
                }
            }

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Label {
                        text: qsTr("Recent mount history")
                        font.bold: true
                    }
                    Label {
                        visible: mgr.recent_mounts.length === 0
                        text: qsTr("History empties when you uninstall.")
                        color: palette.placeholderText
                    }
                    Repeater {
                        model: mgr.recent_mounts
                        delegate: Label {
                            text: modelData
                            font.family: "monospace"
                        }
                    }
                }
            }
        }
    }
}
