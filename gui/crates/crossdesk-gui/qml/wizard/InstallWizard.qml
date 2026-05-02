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
        initialItem: step1
    }

    Step1Iso {
        id: step1
        wizard: page.wizard
        onNext: stepStack.push(step2)
    }
    Step2Identity {
        id: step2
        wizard: page.wizard
        onBack: stepStack.pop()
        onNext: stepStack.push(step3)
    }
    Step3Resources {
        id: step3
        wizard: page.wizard
        onBack: stepStack.pop()
        onInstall: {
            wizard.start_install();
            stepStack.push(progressView);
        }
    }
    ProgressView {
        id: progressView
        wizard: page.wizard
        onClose: {
            wizard.reset();
            page.rootStack.pop();
        }
    }
}
