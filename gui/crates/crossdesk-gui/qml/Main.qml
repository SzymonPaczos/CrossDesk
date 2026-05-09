import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

ApplicationWindow {
    id: root
    width: 800
    height: 600
    visible: true
    title: qsTr("CrossDesk Manager")

    // Route between landing (no VM yet), wizard (installing), and the
    // full Manager (post-install). Phase 6 wires the route based on
    // an install-state flag the daemon would expose; for the dev mode
    // the user clicks "Open Manager" or "New Windows VM".

    WizardState {
        id: wizard
    }

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 12

            Label {
                text: qsTr("CrossDesk Manager")
                font.pixelSize: 16
                font.bold: true
                Layout.leftMargin: 12
            }

            Item { Layout.fillWidth: true }

            Label {
                text: qsTr("Language:")
            }
            ComboBox {
                id: langSwitch
                model: ["en", "pl"]
                Layout.rightMargin: 12
            }
        }
    }

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: landingComponent
    }

    Component {
        id: landingComponent
        Item {
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 16

                Label {
                    text: qsTr("Welcome to CrossDesk")
                    font.pixelSize: 22
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }

                Label {
                    text: qsTr("Provision a Windows guest to get started, or open the Manager if you've already installed.")
                    color: palette.placeholderText
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    Layout.preferredWidth: 400
                }

                RowLayout {
                    spacing: 12
                    Layout.alignment: Qt.AlignHCenter

                    Button {
                        text: qsTr("New Windows VM")
                        onClicked: {
                            wizard.reset();
                            stack.push("qrc:/qt/qml/com/crossdesk/gui/qml/wizard/InstallWizard.qml", {
                                "wizard": wizard,
                                "rootStack": stack
                            });
                        }
                    }

                    Button {
                        text: qsTr("Open Manager")
                        onClicked: stack.push("qrc:/qt/qml/com/crossdesk/gui/qml/manager/Manager.qml")
                    }
                }
            }
        }
    }
}
