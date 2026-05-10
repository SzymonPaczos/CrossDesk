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

    // Phase 6 (mock): hardcoded true → Manager opens directly.
    // Phase 7 Week 27: replace with mgmt::Status has_vm field from daemon.
    readonly property bool hasVm: true

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
        initialItem: "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Manager.qml"

        Component.onCompleted: {
            if (!root.hasVm) {
                wizard.reset();
                stack.push("qrc:/qt/qml/com/crossdesk/gui/qml/wizard/InstallWizard.qml", {
                    "wizard": wizard,
                    "rootStack": stack
                });
            }
        }
    }
}
