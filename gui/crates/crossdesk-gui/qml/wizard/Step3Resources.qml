import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: step
    property var wizard
    signal back()
    signal install()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Label {
            text: qsTr("Step 3 of 3 — Hardware resources")
            font.pixelSize: 18
            font.bold: true
        }

        Label {
            text: qsTr("Defaults are tuned for development workloads. Production tuning is out of scope for the wizard.")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        GridLayout {
            columns: 3
            rowSpacing: 12
            columnSpacing: 12
            Layout.fillWidth: true

            Label { text: qsTr("RAM") }
            Slider {
                from: 2; to: 32; stepSize: 1
                value: wizard.ram_gb
                Layout.fillWidth: true
                onMoved: wizard.ram_gb = value
            }
            Label { text: qsTr("%1 GB").arg(wizard.ram_gb) }

            Label { text: qsTr("vCPU") }
            Slider {
                from: 2; to: 16; stepSize: 1
                value: wizard.vcpu
                Layout.fillWidth: true
                onMoved: wizard.vcpu = value
            }
            Label { text: qsTr("%1 cores").arg(wizard.vcpu) }

            Label { text: qsTr("Disk") }
            Slider {
                from: 40; to: 500; stepSize: 10
                value: wizard.disk_gb
                Layout.fillWidth: true
                onMoved: wizard.disk_gb = value
            }
            Label { text: qsTr("%1 GB").arg(wizard.disk_gb) }
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
                text: qsTr("Install")
                highlighted: true
                onClicked: step.install()
            }
        }
    }
}
