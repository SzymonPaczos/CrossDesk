import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: step
    property var wizard
    signal back()
    signal next()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Label {
            text: qsTr("Step 2 of 3 — VM identity")
            font.pixelSize: 18
            font.bold: true
        }

        Label {
            text: qsTr("These values are baked into autounattend.xml. The guest will boot pre-named and pre-localized.")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        GridLayout {
            columns: 2
            rowSpacing: 12
            columnSpacing: 12
            Layout.fillWidth: true

            Label { text: qsTr("VM name") }
            TextField {
                text: wizard.vm_name
                Layout.fillWidth: true
                onTextEdited: wizard.vm_name = text
            }

            Label { text: qsTr("Timezone") }
            ComboBox {
                model: ["Europe/Warsaw", "Europe/London", "America/New_York", "Asia/Tokyo", "UTC"]
                currentIndex: Math.max(0, model.indexOf(wizard.timezone))
                Layout.fillWidth: true
                onActivated: wizard.timezone = currentText
            }

            Label { text: qsTr("Locale") }
            ComboBox {
                model: ["en-US", "en-GB", "pl-PL", "de-DE", "ja-JP"]
                currentIndex: Math.max(0, model.indexOf(wizard.locale))
                Layout.fillWidth: true
                onActivated: wizard.locale = currentText
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8

            Button {
                text: qsTr("Back")
                onClicked: step.back()
            }
            Button {
                text: qsTr("Next")
                enabled: wizard.vm_name.length > 0
                onClicked: step.next()
            }
        }
    }
}
