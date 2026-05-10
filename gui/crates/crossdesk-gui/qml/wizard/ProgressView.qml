import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    property var wizard
    signal close()

    Timer {
        id: tick
        // Each Rust step reports its own duration; we re-arm with the next
        // step's duration after every fire. `running: wizard.installing` ties
        // the timer's lifetime to the install state so a parallel
        // start_install() (e.g. accidental double-click) does not produce two
        // racing timers — the second start is a no-op on the Rust side.
        interval: wizard.current_step_duration_ms()
        running: wizard.installing
        repeat: false
        onTriggered: {
            if (!wizard.installing) {
                return;
            }
            wizard.advance();
            if (wizard.installing) {
                interval = wizard.current_step_duration_ms();
                restart();
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: palette.window
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 0
        width: Math.min(parent.width * 0.7, 520)

        // Progress card
        Rectangle {
            Layout.fillWidth: true
            color: palette.base
            border.color: palette.mid
            border.width: 1
            radius: 6
            implicitHeight: progressCardContent.implicitHeight + 28

            ColumnLayout {
                id: progressCardContent
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 20
                spacing: 16

                Label {
                    text: wizard.finished
                          ? qsTr("Installation complete")
                          : qsTr("Installing %1…").arg(wizard.vm_name)
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: palette.text
                    font.letterSpacing: -0.2
                    Layout.alignment: Qt.AlignHCenter
                }

                // Progress bar track
                Rectangle {
                    Layout.fillWidth: true
                    height: 4
                    radius: 2
                    color: palette.mid

                    Rectangle {
                        id: progressFill
                        height: parent.height
                        radius: 2
                        color: wizard.finished ? "#4caf50" : palette.highlight

                        // Indeterminate animation when installing and progress_pct is 0
                        width: wizard.finished
                               ? parent.width
                               : (wizard.progress_pct > 0
                                  ? parent.width * (wizard.progress_pct / 100.0)
                                  : parent.width * 0.35)

                        NumberAnimation on x {
                            running: wizard.installing && wizard.progress_pct === 0
                            loops: Animation.Infinite
                            from: -progressFill.width
                            to: progressFill.parent.width
                            duration: 1600
                            easing.type: Easing.InOutSine
                        }
                    }
                }

                // Status line
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 8

                    Rectangle {
                        visible: wizard.installing
                        width: 14; height: 14; radius: 7
                        color: "transparent"
                        border.color: palette.highlight
                        border.width: 2

                        RotationAnimator on rotation {
                            running: wizard.installing
                            loops: Animation.Infinite
                            from: 0; to: 360
                            duration: 900
                        }
                    }

                    Label {
                        text: qsTr(wizard.progress_label)
                        font.pixelSize: 13
                        color: palette.placeholderText
                    }
                }

                Label {
                    text: qsTr("Step %1 of %2")
                        .arg(Math.min(wizard.current_step + 1, wizard.total_steps))
                        .arg(wizard.total_steps)
                    Layout.alignment: Qt.AlignHCenter
                    visible: !wizard.finished
                    font.pixelSize: 12
                    color: palette.placeholderText
                }

                Button {
                    text: qsTr("Close")
                    visible: wizard.finished
                    highlighted: true
                    Layout.alignment: Qt.AlignHCenter
                    onClicked: view.close()
                }
            }
        }
    }
}
