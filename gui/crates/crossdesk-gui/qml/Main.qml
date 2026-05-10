import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

ApplicationWindow {
    id: root
    width: 1100
    height: 760
    minimumWidth: 860
    minimumHeight: 560
    visible: true
    title: qsTr("CrossDesk Manager")

    WizardState {
        id: wizard
    }

    function launchWizard() {
        wizard.reset();
        stack.push("qrc:/qt/qml/com/crossdesk/gui/qml/wizard/InstallWizard.qml", {
            "wizard": wizard,
            "rootStack": stack
        });
    }

    // Window chrome bar
    header: Rectangle {
        height: 36
        color: palette.alternateBase

        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 1
            color: palette.mid
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 8

            // Window title (centered)
            Item { Layout.fillWidth: true }
            Label {
                text: qsTr("CrossDesk Manager")
                font.pixelSize: 12
                font.weight: Font.Medium
                color: palette.placeholderText
            }
            Item { Layout.fillWidth: true }
        }
    }

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Manager.qml"
    }
}
