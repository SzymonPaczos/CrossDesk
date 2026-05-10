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
        spacing: 0

        // ── Step body ─────────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width

            ColumnLayout {
                width: step.width
                spacing: 20

                Item { height: 4 }

                ColumnLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 4

                    Label {
                        text: qsTr("Step 2 of 3 — VM identity")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        font.letterSpacing: -0.3
                    }
                    Label {
                        text: qsTr("These values are baked into autounattend.xml. The guest will boot pre-named and pre-localized.")
                        color: palette.placeholderText
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Fields card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: fieldsLayout.implicitHeight + 28

                    GridLayout {
                        id: fieldsLayout
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 16
                        columns: 2
                        rowSpacing: 16
                        columnSpacing: 16

                        Label {
                            text: qsTr("VM name")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            Layout.preferredWidth: 120
                        }
                        TextField {
                            text: wizard.vm_name
                            Layout.fillWidth: true
                            font.pixelSize: 12
                            onTextEdited: wizard.vm_name = text
                            placeholderText: qsTr("e.g. Windows-11")
                        }

                        Label {
                            text: qsTr("Timezone")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                        }
                        ComboBox {
                            model: ["Europe/Warsaw", "Europe/London", "America/New_York", "Asia/Tokyo", "UTC"]
                            currentIndex: Math.max(0, model.indexOf(wizard.timezone))
                            Layout.fillWidth: true
                            font.pixelSize: 12
                            onActivated: wizard.timezone = currentText
                        }

                        Label {
                            text: qsTr("Locale")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                        }
                        ComboBox {
                            model: ["en-US", "en-GB", "pl-PL", "de-DE", "ja-JP"]
                            currentIndex: Math.max(0, model.indexOf(wizard.locale))
                            Layout.fillWidth: true
                            font.pixelSize: 12
                            onActivated: wizard.locale = currentText
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ── Sticky footer ─────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 52
            color: palette.alternateBase

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: palette.mid
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: 8

                Button {
                    text: qsTr("Back")
                    onClicked: step.back()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Next")
                    highlighted: true
                    enabled: wizard.vm_name.length > 0
                    onClicked: step.next()
                }
            }
        }
    }
}
