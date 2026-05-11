import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    id: page
    property var wizard
    property var rootStack

    title: qsTr("Install Windows VM")

    // Remove the default Page header — we provide our own
    header: null

    background: Rectangle { color: palette.window }

    StackView {
        id: stepStack
        anchors.fill: parent
        initialItem: step1Component
    }

    Component {
        id: step1Component
        Step1Iso {
            wizard: page.wizard
            onInstall: {
                page.wizard.start_install();
                stepStack.push(progressComponent);
            }
            onCancel: page.rootStack.pop()
        }
    }
    Component {
        id: progressComponent
        ProgressView {
            wizard: page.wizard
            onClose: {
                page.wizard.reset();
                page.rootStack.pop();
            }
        }
    }
}
