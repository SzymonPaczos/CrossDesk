import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: lifecycle
    property string paneId: "lifecycle"

    ManagerState { id: mgr }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: lifecycle.width - 32
            spacing: 16

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 12

                    Label {
                        text: qsTr("VM controls")
                        font.bold: true
                    }
                    Label {
                        text: qsTr("● %1").arg(mgr.vm_state)
                    }

                    RowLayout {
                        spacing: 8
                        Button { text: qsTr("Suspend"); onClicked: mgr.suspend() }
                        Button { text: qsTr("Resume"); onClicked: mgr.resume() }
                        Button {
                            text: qsTr("Force HARD_DESTROY")
                            onClicked: confirmHardDestroy.open()
                        }
                    }
                }
            }

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8

                    Label {
                        text: qsTr("FSM state")
                        font.bold: true
                    }
                    Label {
                        text: mgr.fsm_state
                        font.family: "monospace"
                    }
                    Label {
                        text: qsTr("EWMA RTT: %1 ms   miss_count: %2   soft_attempts: %3")
                            .arg(mgr.ewma_rtt_ms)
                            .arg(mgr.miss_count)
                            .arg(mgr.soft_attempts)
                        font.family: "monospace"
                        color: palette.placeholderText
                    }
                }
            }
        }
    }

    Dialog {
        id: confirmHardDestroy
        title: qsTr("Force HARD_DESTROY?")
        modal: true
        standardButtons: Dialog.Yes | Dialog.No
        anchors.centerIn: parent

        Label {
            text: qsTr("This will force-restart the VM. Any unsaved Windows app state will be lost.")
            wrapMode: Text.WordWrap
            width: 320
        }

        onAccepted: mgr.hard_destroy()
    }
}
