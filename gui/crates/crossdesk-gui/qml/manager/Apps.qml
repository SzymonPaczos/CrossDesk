import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: apps
    property string paneId: "apps"

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
                text: qsTr("Apps")
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: palette.text
                font.letterSpacing: -0.3
            }
        }

        // ── Toolbar ───────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 46
            color: palette.window

            Rectangle {
                anchors.bottom: parent.bottom
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

                TextField {
                    placeholderText: qsTr("Search apps…")
                    font.pixelSize: 12
                    Layout.preferredWidth: 220
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Refresh discovery")
                    onClicked: mgr.refresh()
                }

                Button {
                    text: qsTr("+ Add custom .exe")
                    highlighted: true
                }
            }
        }

        // ── App grid ──────────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width

            ColumnLayout {
                width: apps.width
                Layout.margins: 24
                spacing: 16

                // Curated apps card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    // Dynamic height: header + grid
                    implicitHeight: cardHeader.height + appGridItem.implicitHeight + 28

                    Rectangle {
                        id: cardHeader
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
                                text: qsTr("Curated apps")
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                            Item { Layout.fillWidth: true }
                            Rectangle {
                                width: badgeLabel.implicitWidth + 14
                                height: 20
                                radius: 10
                                color: palette.mid

                                Label {
                                    id: badgeLabel
                                    anchors.centerIn: parent
                                    text: mgr.curated_apps.length
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    color: palette.placeholderText
                                }
                            }
                        }
                    }

                    GridLayout {
                        id: appGridItem
                        anchors.top: cardHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        columns: 5
                        rowSpacing: 12
                        columnSpacing: 12

                        Repeater {
                            model: mgr.curated_apps

                            delegate: Rectangle {
                                Layout.preferredWidth: 120
                                Layout.preferredHeight: 130
                                color: palette.window
                                border.color: palette.mid
                                border.width: 1
                                radius: 6

                                readonly property var parts: modelData.split("|")
                                readonly property string appId: parts[0]
                                readonly property string appName: parts[1]
                                readonly property string appCategory: parts[2]
                                readonly property string appStars: parts[3]

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 4

                                    // App icon placeholder — colored rectangle with initial
                                    Rectangle {
                                        Layout.alignment: Qt.AlignHCenter
                                        width: 44
                                        height: 44
                                        radius: 10
                                        color: Qt.hsla(Math.abs(appName.charCodeAt(0) * 37) % 360 / 360.0,
                                                        0.65, 0.45, 1.0)

                                        Label {
                                            anchors.centerIn: parent
                                            text: appName.slice(0, 1)
                                            font.pixelSize: 20
                                            font.weight: Font.Bold
                                            color: "white"
                                        }
                                    }

                                    Label {
                                        text: appName
                                        font.pixelSize: 12
                                        font.weight: Font.Medium
                                        Layout.alignment: Qt.AlignHCenter
                                        horizontalAlignment: Text.AlignHCenter
                                    }
                                    Label {
                                        text: appCategory
                                        color: palette.placeholderText
                                        font.pixelSize: 10
                                        font.family: "monospace"
                                        Layout.alignment: Qt.AlignHCenter
                                        visible: appCategory.length > 0
                                    }

                                    Item { Layout.fillHeight: true }

                                    Button {
                                        text: qsTr("Launch")
                                        Layout.fillWidth: true
                                        onClicked: mgr.launch_app(appId)
                                        font.pixelSize: 11
                                    }
                                }
                            }
                        }
                    }
                }

                // Discovered apps
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    spacing: 8

                    Label {
                        text: qsTr("Discovered (%1)").arg(mgr.discovered_apps.length)
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        topPadding: 8
                    }

                    Label {
                        visible: mgr.discovered_apps.length === 0
                        text: qsTr("No apps discovered yet. Auto-discovery runs after VM is running.")
                        color: palette.placeholderText
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                Item { height: 8 }
            }
        }
    }
}
