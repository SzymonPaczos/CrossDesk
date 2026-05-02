import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

ApplicationWindow {
    id: root
    width: 720
    height: 520
    visible: true
    title: qsTr("CrossDesk Manager")

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
                // i18n switching wires up in src/i18n/mod.rs; the
                // selection here is cosmetic in the first iteration.
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
                    text: qsTr("No virtual machines yet.")
                    font.pixelSize: 18
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }

                Label {
                    text: qsTr("Provision a Windows guest to get started.")
                    color: palette.placeholderText
                    Layout.alignment: Qt.AlignHCenter
                }

                Button {
                    text: qsTr("New Windows VM")
                    Layout.alignment: Qt.AlignHCenter
                    onClicked: {
                        wizard.reset();
                        stack.push("qrc:/qt/qml/com/crossdesk/gui/qml/wizard/InstallWizard.qml", {
                            "wizard": wizard,
                            "rootStack": stack
                        });
                    }
                }
            }
        }
    }
}
