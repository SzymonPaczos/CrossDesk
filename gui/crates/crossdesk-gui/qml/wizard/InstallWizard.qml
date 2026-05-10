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

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Wizard step indicator ─────────────────────────────
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

            // Step dots
            RowLayout {
                anchors.centerIn: parent
                spacing: 0

                Repeater {
                    model: [
                        qsTr("Media"),
                        qsTr("Identity"),
                        qsTr("Resources"),
                    ]

                    delegate: RowLayout {
                        spacing: 0
                        required property string modelData
                        required property int index

                        readonly property int currentStep: {
                            var cur = stepStack.currentItem;
                            if (!cur) return 0;
                            return cur.stepIndex !== undefined ? cur.stepIndex : 0;
                        }
                        readonly property bool isDone: index < currentStep
                        readonly property bool isActive: index === currentStep

                        // Connector line (not before first)
                        Rectangle {
                            visible: index > 0
                            width: 40
                            height: 2
                            radius: 1
                            color: isDone ? palette.highlight : palette.mid
                        }

                        RowLayout {
                            spacing: 6

                            // Step number circle
                            Rectangle {
                                width: 22; height: 22; radius: 11
                                color: isDone ? palette.highlight
                                     : isActive ? "transparent"
                                     : "transparent"
                                border.color: isDone ? palette.highlight
                                            : isActive ? palette.highlight
                                            : palette.mid
                                border.width: 1.5

                                Label {
                                    anchors.centerIn: parent
                                    text: isDone ? "✓" : (index + 1)
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    color: isDone ? "white"
                                         : isActive ? palette.highlight
                                         : palette.placeholderText
                                }
                            }

                            Label {
                                text: modelData
                                font.pixelSize: 12
                                font.weight: isActive ? Font.DemiBold : Font.Normal
                                color: isActive ? palette.text : palette.placeholderText
                            }
                        }
                    }
                }
            }
        }

        // ── Step content ──────────────────────────────────────
        StackView {
            id: stepStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            initialItem: step1Component
        }
    }

    Component {
        id: step1Component
        Step1Iso {
            property int stepIndex: 0
            wizard: page.wizard
            onNext: stepStack.push(step2Component)
            onCancel: page.rootStack.pop()
        }
    }
    Component {
        id: step2Component
        Step2Identity {
            property int stepIndex: 1
            wizard: page.wizard
            onBack: stepStack.pop()
            onNext: stepStack.push(step3Component)
        }
    }
    Component {
        id: step3Component
        Step3Resources {
            property int stepIndex: 2
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
