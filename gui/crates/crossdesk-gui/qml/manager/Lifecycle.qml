import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: lifecycle
    property string paneId: "lifecycle"

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
                text: qsTr("Lifecycle")
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
                width: lifecycle.width
                Layout.margins: 24
                spacing: 16

                // VM controls card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: ctrlHeader.height + ctrlBody.implicitHeight + 28

                    Rectangle {
                        id: ctrlHeader
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
                            text: qsTr("VM controls")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: ctrlBody
                        anchors.top: ctrlHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 14

                        // Status row
                        RowLayout {
                            spacing: 10
                            Rectangle {
                                width: 12; height: 12; radius: 6
                                color: "#4caf50"
                            }
                            Label {
                                text: qsTr("<b>Running</b> · %1").arg(mgr.vm_state)
                                textFormat: Text.RichText
                                font.pixelSize: 13
                            }
                        }

                        // Separator
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: palette.mid
                            opacity: 0.5
                        }

                        // Action buttons
                        RowLayout {
                            spacing: 8
                            Button {
                                text: qsTr("Suspend")
                                onClicked: mgr.suspend()
                            }
                            Button {
                                text: qsTr("Resume")
                                onClicked: mgr.resume()
                            }
                            Button {
                                text: qsTr("Force HARD_DESTROY")
                                onClicked: confirmHardDestroy.open()
                                // Danger styling — red text via palette override is not possible
                                // without subclassing; rely on the label for visual cue
                            }
                        }
                    }
                }

                // FSM state card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: fsmHeader.height + fsmBody.implicitHeight + 28

                    Rectangle {
                        id: fsmHeader
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
                            text: qsTr("FSM state")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: fsmBody
                        anchors.top: fsmHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 12

                        Label {
                            text: mgr.fsm_state
                            font.family: "monospace"
                            font.pixelSize: 14
                            font.weight: Font.Bold
                            color: palette.highlight
                            font.letterSpacing: 0.8
                        }

                        // FSM metrics
                        Rectangle {
                            Layout.fillWidth: true
                            height: fsmMetrics.implicitHeight + 16
                            color: Qt.rgba(palette.mid.r, palette.mid.g, palette.mid.b, 0.3)
                            radius: 5

                            RowLayout {
                                id: fsmMetrics
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 28

                                ColumnLayout {
                                    spacing: 2
                                    Label {
                                        text: qsTr("EWMA RTT")
                                        font.pixelSize: 10
                                        color: palette.placeholderText
                                        font.capitalization: Font.AllUppercase
                                        font.letterSpacing: 0.4
                                    }
                                    Label {
                                        text: mgr.ewma_rtt_ms + " ms"
                                        font.family: "monospace"
                                        font.pixelSize: 12
                                    }
                                }

                                ColumnLayout {
                                    spacing: 2
                                    Label {
                                        text: qsTr("miss_count")
                                        font.pixelSize: 10
                                        color: palette.placeholderText
                                        font.capitalization: Font.AllUppercase
                                        font.letterSpacing: 0.4
                                    }
                                    Label {
                                        text: mgr.miss_count
                                        font.family: "monospace"
                                        font.pixelSize: 12
                                    }
                                }

                                ColumnLayout {
                                    spacing: 2
                                    Label {
                                        text: qsTr("soft_attempts")
                                        font.pixelSize: 10
                                        color: palette.placeholderText
                                        font.capitalization: Font.AllUppercase
                                        font.letterSpacing: 0.4
                                    }
                                    Label {
                                        text: mgr.soft_attempts
                                        font.family: "monospace"
                                        font.pixelSize: 12
                                    }
                                }

                                Item { Layout.fillWidth: true }
                            }
                        }
                    }
                }

                Item { height: 8 }
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
