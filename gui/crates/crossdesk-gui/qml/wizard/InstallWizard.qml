import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    id: page
    property var wizard
    property var rootStack

    title: qsTr("Install Windows VM")

    StackView {
        id: stepStack
        anchors.fill: parent
        initialItem: step1Component
    }

    Component {
        id: step1Component
        Step1Iso {
            wizard: page.wizard
            onNext: stepStack.push(step2Component)
            onCancel: page.rootStack.pop()
        }
    }
    Component {
        id: step2Component
        Step2Identity {
            wizard: page.wizard
            onBack: stepStack.pop()
            onNext: stepStack.push(step3Component)
        }
    }
    Component {
        id: step3Component
        Step3Resources {
            wizard: page.wizard
            onBack: stepStack.pop()
            onInstall: {
                page.wizard.start_install();
                stepStack.push(progressComponent);
            }
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
