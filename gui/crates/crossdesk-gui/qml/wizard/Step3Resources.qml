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
                        text: qsTr("Step 3 of 3 — Hardware resources")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        font.letterSpacing: -0.3
                    }
                    Label {
                        text: qsTr("Defaults are tuned for development workloads. Production tuning is out of scope for the wizard.")
                        color: palette.placeholderText
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Resource sliders card
                ColumnLayout {
                    Layout.leftMargin: 32
                    Layout.rightMargin: 32
                    spacing: 12

                    // RAM block
                    Rectangle {
                        Layout.fillWidth: true
                        color: palette.base
                        border.color: palette.mid
                        border.width: 1
                        radius: 6
                        implicitHeight: ramBlock.implicitHeight + 28

                        ColumnLayout {
                            id: ramBlock
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 16
                            spacing: 8

                            RowLayout {
                                Label {
                                    text: qsTr("RAM")
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                }
                                Item { Layout.fillWidth: true }
                                Label {
                                    text: qsTr("%1 GB").arg(wizard.ram_gb)
                                    font.family: "monospace"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: palette.highlight
                                }
                            }

                            Slider {
                                from: 2; to: 32; stepSize: 1
                                value: wizard.ram_gb
                                Layout.fillWidth: true
                                onMoved: wizard.ram_gb = value
                            }

                            Label {
                                text: qsTr("Minimum 4 GB recommended for Windows 11.")
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
                        }
                    }

                    // vCPU block
                    Rectangle {
                        Layout.fillWidth: true
                        color: palette.base
                        border.color: palette.mid
                        border.width: 1
                        radius: 6
                        implicitHeight: vcpuBlock.implicitHeight + 28

                        ColumnLayout {
                            id: vcpuBlock
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 16
                            spacing: 8

                            RowLayout {
                                Label {
                                    text: qsTr("vCPU")
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                }
                                Item { Layout.fillWidth: true }
                                Label {
                                    text: qsTr("%1 cores").arg(wizard.vcpu)
                                    font.family: "monospace"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: palette.highlight
                                }
                            }

                            Slider {
                                from: 2; to: 16; stepSize: 1
                                value: wizard.vcpu
                                Layout.fillWidth: true
                                onMoved: wizard.vcpu = value
                            }

                            Label {
                                text: qsTr("Shares physical cores — does not subtract from host.")
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
                        }
                    }

                    // Disk block
                    Rectangle {
                        Layout.fillWidth: true
                        color: palette.base
                        border.color: palette.mid
                        border.width: 1
                        radius: 6
                        implicitHeight: diskBlock.implicitHeight + 28

                        ColumnLayout {
                            id: diskBlock
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 16
                            spacing: 8

                            RowLayout {
                                Label {
                                    text: qsTr("Disk")
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                }
                                Item { Layout.fillWidth: true }
                                Label {
                                    text: qsTr("%1 GB").arg(wizard.disk_gb)
                                    font.family: "monospace"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: palette.highlight
                                }
                            }

                            Slider {
                                from: 40; to: 500; stepSize: 10
                                value: wizard.disk_gb
                                Layout.fillWidth: true
                                onMoved: wizard.disk_gb = value
                            }

                            Label {
                                text: qsTr("Thin-provisioned qcow2 — only used space is allocated.")
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
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
                    text: qsTr("Install")
                    highlighted: true
                    onClicked: step.install()
                }
            }
        }
    }
}
