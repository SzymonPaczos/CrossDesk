import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: root
    anchors.fill: parent

    ManagerState {
        id: mgr
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── Sidebar ───────────────────────────────────────────
        Rectangle {
            id: sidebar
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            color: palette.alternateBase

            // Right border
            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: palette.mid
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Brand header
                Rectangle {
                    Layout.fillWidth: true
                    height: 52
                    color: "transparent"

                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 1
                        color: palette.mid
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 12
                        spacing: 10

                        // Crossdesk logo mark
                        Rectangle {
                            width: 24
                            height: 24
                            radius: 6
                            color: palette.highlight

                            Rectangle {
                                x: 4; y: 5
                                width: 11; height: 9
                                color: "white"
                                opacity: 1.0
                            }
                            Rectangle {
                                x: 9; y: 10
                                width: 11; height: 9
                                color: "black"
                                opacity: 0.5
                            }
                        }

                        ColumnLayout {
                            spacing: 1
                            Label {
                                text: "CrossDesk"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: palette.text
                            }
                            Label {
                                text: qsTr("Manager")
                                font.pixelSize: 11
                                color: palette.placeholderText
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }
                }

                // "MANAGE" section label
                Item {
                    Layout.fillWidth: true
                    height: 30
                    Label {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 4
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: qsTr("MANAGE")
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: palette.placeholderText
                        font.letterSpacing: 0.8
                    }
                }

                Repeater {
                    id: manageItems
                    model: [
                        { id: "dashboard", label: qsTr("Dashboard"), icon: "qrc:/icons/dashboard.svg" },
                        { id: "apps",      label: qsTr("Apps"),      icon: "qrc:/icons/apps.svg" },
                        { id: "storage",   label: qsTr("Storage"),   icon: "qrc:/icons/storage.svg" },
                        { id: "lifecycle", label: qsTr("Lifecycle"), icon: "qrc:/icons/lifecycle.svg" },
                    ]

                    delegate: Item {
                        required property var modelData
                        Layout.fillWidth: true
                        height: 34

                        readonly property bool isActive:
                            stack.currentItem && stack.currentItem.paneId === modelData.id

                        // Accent indicator bar
                        Rectangle {
                            id: accentBar
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.topMargin: 6
                            anchors.bottomMargin: 6
                            width: 3
                            radius: 2
                            color: palette.highlight
                            visible: parent.isActive
                        }

                        Rectangle {
                            id: itemBg
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 6
                            radius: 4
                            color: parent.isActive
                                   ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.12)
                                   : hoverHandler.hovered
                                     ? Qt.rgba(palette.mid.r, palette.mid.g, palette.mid.b, 0.6)
                                     : "transparent"
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 10
                            spacing: 10

                            Image {
                                source: modelData.icon
                                width: 18
                                height: 18
                                sourceSize: Qt.size(18, 18)
                                // Tint active icon with highlight, inactive with muted text
                                // (SVGs use currentColor but QML Image doesn't support that
                                //  directly — colorize does the same job)
                                layer.enabled: true
                                layer.effect: null   // rendered as-is; relies on SVG currentColor default (black)
                                opacity: parent.parent.isActive ? 1.0 : 0.55
                            }

                            Label {
                                text: modelData.label
                                font.pixelSize: 12
                                font.weight: parent.parent.parent.isActive ? Font.DemiBold : Font.Normal
                                color: parent.parent.parent.isActive ? palette.highlight : palette.text
                                Layout.fillWidth: true
                            }
                        }

                        HoverHandler { id: hoverHandler }

                        TapHandler {
                            onTapped: stack.replace(paneSource(modelData.id))
                        }
                    }
                }

                // "SYSTEM" section label
                Item {
                    Layout.fillWidth: true
                    height: 30
                    Label {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 4
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: qsTr("SYSTEM")
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: palette.placeholderText
                        font.letterSpacing: 0.8
                    }
                }

                Repeater {
                    id: systemItems
                    model: [
                        { id: "diagnose",  label: qsTr("Diagnose"),  icon: "qrc:/icons/diagnose.svg" },
                        { id: "logs",      label: qsTr("Logs"),      icon: "qrc:/icons/logs.svg" },
                        { id: "settings",  label: qsTr("Settings"),  icon: "qrc:/icons/settings.svg" },
                        { id: "about",     label: qsTr("About"),     icon: "qrc:/icons/about.svg" },
                    ]

                    delegate: Item {
                        required property var modelData
                        Layout.fillWidth: true
                        height: 34

                        readonly property bool isActive:
                            stack.currentItem && stack.currentItem.paneId === modelData.id

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.topMargin: 6
                            anchors.bottomMargin: 6
                            width: 3
                            radius: 2
                            color: palette.highlight
                            visible: parent.isActive
                        }

                        Rectangle {
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 6
                            radius: 4
                            color: parent.isActive
                                   ? Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.12)
                                   : hoverHandler2.hovered
                                     ? Qt.rgba(palette.mid.r, palette.mid.g, palette.mid.b, 0.6)
                                     : "transparent"
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 10
                            spacing: 10

                            Image {
                                source: modelData.icon
                                width: 18
                                height: 18
                                sourceSize: Qt.size(18, 18)
                                opacity: parent.parent.parent.isActive ? 1.0 : 0.55
                            }

                            Label {
                                text: modelData.label
                                font.pixelSize: 12
                                font.weight: parent.parent.parent.isActive ? Font.DemiBold : Font.Normal
                                color: parent.parent.parent.isActive ? palette.highlight : palette.text
                                Layout.fillWidth: true
                            }
                        }

                        HoverHandler { id: hoverHandler2 }

                        TapHandler {
                            onTapped: stack.replace(paneSource(modelData.id))
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ── Main pane ─────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // State 1: VM installed + daemon connected → normal panes
            StackView {
                id: stack
                anchors.fill: parent
                visible: mgr.has_vm && mgr.daemon_connected
                initialItem: (mgr.has_vm && mgr.daemon_connected)
                    ? "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Dashboard.qml"
                    : ""
            }

            // State 2: VM installed but daemon not running
            Rectangle {
                anchors.fill: parent
                visible: mgr.has_vm && !mgr.daemon_connected
                color: palette.window

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 12

                    // Warning icon placeholder
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 56; height: 56; radius: 14
                        color: Qt.rgba(palette.highlight.r, palette.highlight.g, palette.highlight.b, 0.12)
                        border.color: palette.mid
                        border.width: 1

                        Label {
                            anchors.centerIn: parent
                            text: "⚠"
                            font.pixelSize: 28
                            color: palette.placeholderText
                        }
                    }

                    Label {
                        text: qsTr("Daemon not running")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Label {
                        text: qsTr("Windows VM is installed but the host daemon is not running.")
                        font.pixelSize: 13
                        color: palette.placeholderText
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Label {
                        text: qsTr("Start it with:")
                        font.pixelSize: 12
                        color: palette.placeholderText
                        Layout.alignment: Qt.AlignHCenter
                    }

                    // Command hint box
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        color: palette.base
                        border.color: palette.mid
                        border.width: 1
                        radius: 4
                        implicitWidth: cmdLabel.implicitWidth + 24
                        implicitHeight: cmdLabel.implicitHeight + 12

                        Label {
                            id: cmdLabel
                            anchors.centerIn: parent
                            text: "systemctl --user start crossdesk-host"
                            font.family: "monospace"
                            font.pixelSize: 12
                            color: palette.text
                        }
                    }

                    Item { height: 4 }

                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 8

                        Button {
                            text: qsTr("Retry connection")
                            onClicked: mgr.refresh()
                        }
                        Button {
                            text: qsTr("Open setup wizard")
                            onClicked: ApplicationWindow.window.launchWizard()
                        }
                    }
                }
            }

            // State 3: No VM installed (wizard was dismissed or has_vm=false fallback)
            Rectangle {
                anchors.fill: parent
                visible: !mgr.has_vm
                color: palette.window

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 16

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 56; height: 56; radius: 14
                        color: palette.highlight

                        Rectangle {
                            x: 10; y: 12; width: 24; height: 20
                            color: "white"; opacity: 1.0
                        }
                        Rectangle {
                            x: 22; y: 24; width: 24; height: 20
                            color: "black"; opacity: 0.45
                        }
                    }

                    Label {
                        text: qsTr("No Windows VM installed")
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        color: palette.text
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Label {
                        text: qsTr("Run the setup wizard to provision a Windows guest.")
                        font.pixelSize: 13
                        color: palette.placeholderText
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Button {
                        text: qsTr("Open setup wizard")
                        highlighted: true
                        Layout.alignment: Qt.AlignHCenter
                        onClicked: ApplicationWindow.window.launchWizard()
                    }
                }
            }
        }
    }

    function paneSource(id) {
        switch (id) {
            case "dashboard": return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Dashboard.qml";
            case "apps":      return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Apps.qml";
            case "storage":   return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Storage.qml";
            case "lifecycle": return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Lifecycle.qml";
            case "diagnose":  return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Diagnose.qml";
            case "logs":      return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Logs.qml";
            case "settings":  return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Settings.qml";
            case "about":     return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/About.qml";
        }
        return "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Dashboard.qml";
    }

    property alias mgrInstance: mgr
}
