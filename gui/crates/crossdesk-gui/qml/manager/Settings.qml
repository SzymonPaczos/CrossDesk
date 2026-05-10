import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: settings
    property string paneId: "settings"

    ManagerState { id: mgr }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Pane header ───────────────────────────────────────
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

            Label {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 24
                text: qsTr("Settings")
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: palette.text
                font.letterSpacing: -0.3
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width

            ColumnLayout {
                width: settings.width
                Layout.margins: 24
                spacing: 16

                // ── General section ───────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: genHeader.height + genBody.implicitHeight + 28

                    Rectangle {
                        id: genHeader
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 38
                        color: "transparent"
                        radius: 6

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            color: palette.mid
                        }

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            text: qsTr("General")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: genBody
                        anchors.top: genHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            RowLayout {
                                spacing: 16
                                Label {
                                    text: qsTr("Language")
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    Layout.preferredWidth: 180
                                }
                                ComboBox {
                                    id: langCombo
                                    model: ["auto", "en", "pl"]
                                    currentIndex: model.indexOf(mgr.language)
                                    onActivated: (index) => mgr.apply_language(model[index])
                                    font.pixelSize: 12
                                    Layout.preferredWidth: 120
                                }
                            }
                            Label {
                                visible: mgr.language !== "auto"
                                text: qsTr("Language change takes effect on next launch.")
                                color: palette.placeholderText
                                font.pixelSize: 11
                                leftPadding: 196
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            RowLayout {
                                spacing: 16
                                ColumnLayout {
                                    spacing: 2
                                    Layout.preferredWidth: 180
                                    Label {
                                        text: qsTr("Theme")
                                        font.pixelSize: 12
                                        font.weight: Font.Medium
                                    }
                                    Label {
                                        text: qsTr("Follows desktop colour scheme by default.")
                                        font.pixelSize: 11
                                        color: palette.placeholderText
                                        wrapMode: Text.WordWrap
                                    }
                                }
                                ComboBox {
                                    model: ["system", "light", "dark"]
                                    currentIndex: model.indexOf(mgr.theme)
                                    onActivated: (index) => mgr.apply_theme(model[index])
                                    font.pixelSize: 12
                                    Layout.preferredWidth: 120
                                }
                            }
                            Label {
                                visible: mgr.theme !== "system"
                                text: qsTr("Light/dark override takes effect on next launch.")
                                color: palette.placeholderText
                                font.pixelSize: 11
                                leftPadding: 196
                            }
                        }

                        RowLayout {
                            spacing: 16
                            ColumnLayout {
                                spacing: 2
                                Layout.preferredWidth: 180
                                Label {
                                    text: qsTr("Anonymous telemetry")
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                }
                                Label {
                                    text: qsTr("Helps prioritise fixes. Off by default.")
                                    font.pixelSize: 11
                                    color: palette.placeholderText
                                }
                            }
                            CheckBox {
                                checked: mgr.telemetry_enabled
                            }
                        }
                    }
                }

                // ── VM section ────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: vmHeader.height + vmBody.implicitHeight + 28

                    Rectangle {
                        id: vmHeader
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 38
                        color: "transparent"
                        radius: 6

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            color: palette.mid
                        }

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            text: qsTr("VM")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: vmBody
                        anchors.top: vmHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 12

                        RowLayout {
                            spacing: 16
                            Label {
                                text: qsTr("Credentials")
                                font.pixelSize: 12
                                font.weight: Font.Medium
                                Layout.preferredWidth: 180
                            }
                            RowLayout {
                                spacing: 6
                                Button { text: qsTr("Show");   font.pixelSize: 11 }
                                Button { text: qsTr("Rotate"); font.pixelSize: 11; onClicked: mgr.rotate_credentials() }
                                Button { text: qsTr("Repair"); font.pixelSize: 11 }
                            }
                        }

                        RowLayout {
                            spacing: 16
                            ColumnLayout {
                                spacing: 2
                                Layout.preferredWidth: 180
                                Label {
                                    text: qsTr("Lean mode")
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                }
                                Label {
                                    text: qsTr("Rebake VM image with services trimmed (opt-in).")
                                    font.pixelSize: 11
                                    color: palette.placeholderText
                                    wrapMode: Text.WordWrap
                                }
                            }
                            CheckBox {
                                checked: mgr.lean_mode
                            }
                        }
                    }
                }

                // ── Display section ───────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: dispHeader.height + dispBody.implicitHeight + 28

                    Rectangle {
                        id: dispHeader
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 38
                        color: "transparent"
                        radius: 6

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            color: palette.mid
                        }

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            text: qsTr("Display")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: dispBody
                        anchors.top: dispHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 12

                        RowLayout {
                            spacing: 16
                            Label {
                                text: qsTr("HiDPI scale")
                                font.pixelSize: 12
                                font.weight: Font.Medium
                                Layout.preferredWidth: 180
                            }
                            ComboBox {
                                model: ["Auto", "100%", "140%", "180%"]
                                currentIndex: hidpiToIndex(mgr.hidpi_scale)
                                font.pixelSize: 12
                                Layout.preferredWidth: 120
                            }
                        }
                    }
                }

                // ── Advanced section ──────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: advHeader.height + advBody.implicitHeight + 28

                    Rectangle {
                        id: advHeader
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 38
                        color: "transparent"
                        radius: 6

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            color: palette.mid
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14

                            Label {
                                text: qsTr("Advanced — FSM tuning")
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: qsTr("Heartbeat / recovery thresholds")
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
                        }
                    }

                    ColumnLayout {
                        id: advBody
                        anchors.top: advHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 8

                        Label {
                            text: qsTr("These knobs balance false-positive HARD_DESTROY against false-negative hung sessions. Defaults are safe for most users.")
                            color: palette.placeholderText
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            font.pixelSize: 12
                        }
                    }
                }

                Item { height: 8 }
            }
        }
    }

    function hidpiToIndex(scale) {
        switch (scale) {
            case 100: return 1;
            case 140: return 2;
            case 180: return 3;
            default:  return 0;
        }
    }
}
