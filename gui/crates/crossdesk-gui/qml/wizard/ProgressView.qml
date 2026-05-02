import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    property var wizard
    signal close()

    Timer {
        id: tick
        // Each Rust step reports its own duration (5s/10s); the engine
        // re-arms us with the next step's duration after each fire.
        interval: wizard.current_step_duration_ms()
        running: wizard.installing
        repeat: false
        onTriggered: {
            wizard.advance();
            if (wizard.installing) {
                interval = wizard.current_step_duration_ms();
                restart();
            }
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 20
        width: parent.width * 0.7

        Label {
            text: wizard.finished
                  ? qsTr("Installation complete")
                  : qsTr("Installing %1…").arg(wizard.vm_name)
            font.pixelSize: 20
            font.bold: true
            Layout.alignment: Qt.AlignHCenter
        }

        ProgressBar {
            from: 0; to: 100
            value: wizard.progress_pct
            Layout.fillWidth: true
        }

        Label {
            text: qsTr(wizard.progress_label)
            Layout.alignment: Qt.AlignHCenter
            color: palette.placeholderText
        }

        Label {
            text: qsTr("Step %1 of %2").arg(Math.min(wizard.current_step + 1, wizard.total_steps)).arg(wizard.total_steps)
            Layout.alignment: Qt.AlignHCenter
            visible: !wizard.finished
        }

        Button {
            text: qsTr("Close")
            visible: wizard.finished
            Layout.alignment: Qt.AlignHCenter
            onClicked: view.close()
        }
    }
}
