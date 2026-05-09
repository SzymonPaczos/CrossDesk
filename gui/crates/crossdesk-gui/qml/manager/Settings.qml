import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: settings
    property string paneId: "settings"

    ManagerState { id: mgr }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: settings.width - 32
            spacing: 16

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    Label { text: qsTr("General"); font.bold: true }

                    RowLayout {
                        spacing: 8
                        Label { text: qsTr("Language:"); Layout.preferredWidth: 110 }
                        ComboBox {
                            model: ["auto", "en", "pl"]
                            currentIndex: model.indexOf(mgr.language)
                            onActivated: (index) => mgr.apply_language(model[index])
                        }
                    }
                    RowLayout {
                        spacing: 8
                        Label { text: qsTr("Theme:"); Layout.preferredWidth: 110 }
                        ComboBox {
                            model: ["system", "light", "dark"]
                            currentIndex: model.indexOf(mgr.theme)
                            onActivated: (index) => mgr.apply_theme(model[index])
                        }
                    }
                    CheckBox {
                        text: qsTr("Anonymous telemetry")
                        checked: mgr.telemetry_enabled
                    }
                }
            }

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    Label { text: qsTr("VM"); font.bold: true }

                    RowLayout {
                        spacing: 8
                        Label { text: qsTr("Credentials:") }
                        Button { text: qsTr("Show") }
                        Button { text: qsTr("Rotate"); onClicked: mgr.rotate_credentials() }
                        Button { text: qsTr("Repair") }
                    }
                    CheckBox {
                        text: qsTr("Lean mode")
                        checked: mgr.lean_mode
                    }
                }
            }

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    Label { text: qsTr("Display"); font.bold: true }

                    RowLayout {
                        spacing: 8
                        Label { text: qsTr("HiDPI scale:"); Layout.preferredWidth: 110 }
                        ComboBox {
                            model: ["Auto", "100%", "140%", "180%"]
                            currentIndex: hidpiToIndex(mgr.hidpi_scale)
                        }
                    }
                }
            }

            Label {
                text: qsTr("Advanced (FSM tuning)")
                font.bold: true
                topPadding: 8
            }
            Label {
                text: qsTr("These knobs balance false-positive HARD_DESTROY against false-negative hung sessions. Defaults are safe for most users.")
                color: palette.placeholderText
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
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
