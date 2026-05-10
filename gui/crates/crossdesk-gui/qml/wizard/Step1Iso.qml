import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: step
    property var wizard
    signal next()
    signal cancel()

    FileDialog {
        id: fileDialog
        title: qsTr("Select Windows ISO image")
        nameFilters: [qsTr("ISO images (*.iso)"), qsTr("All files (*)")]
        onAccepted: wizard.iso_path = selectedFile.toString()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Label {
            text: qsTr("Step 1 of 3 — Installation media")
            font.pixelSize: 18
            font.bold: true
        }

        Label {
            text: qsTr("Choose the Windows installation ISO. The image will be attached as a virtual CD-ROM during the autounattend bootstrap.")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        RowLayout {
            spacing: 8
            Layout.fillWidth: true

            TextField {
                id: pathField
                text: wizard.iso_path
                placeholderText: qsTr("No ISO selected")
                readOnly: true
                Layout.fillWidth: true
            }

            Button {
                text: qsTr("Browse…")
                onClicked: fileDialog.open()
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Button {
                text: qsTr("Back")
                onClicked: step.cancel()
            }

            Item { Layout.fillWidth: true }

            Button {
                text: qsTr("Next")
                enabled: wizard.iso_path.length > 0
                onClicked: step.next()
            }
        }
    }
}
