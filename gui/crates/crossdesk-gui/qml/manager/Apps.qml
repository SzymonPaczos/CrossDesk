import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: apps
    property string paneId: "apps"

    ManagerState { id: mgr }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: apps.width - 32
            spacing: 16

            Label {
                text: qsTr("Curated apps")
                font.bold: true
                font.pixelSize: 16
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 4
                rowSpacing: 12
                columnSpacing: 12

                Repeater {
                    model: mgr.curated_apps

                    delegate: Frame {
                        Layout.preferredWidth: 160
                        Layout.preferredHeight: 140

                        readonly property var parts: modelData.split("|")
                        readonly property string appId: parts[0]
                        readonly property string appName: parts[1]
                        readonly property string appCategory: parts[2]
                        readonly property string appStars: parts[3]

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 6

                            Label {
                                text: appName
                                font.bold: true
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Label {
                                text: appCategory
                                color: palette.placeholderText
                                font.pixelSize: 10
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Label {
                                text: appStars
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Item { Layout.fillHeight: true }
                            Button {
                                text: qsTr("Launch")
                                Layout.fillWidth: true
                                onClicked: mgr.launch_app(appId)
                            }
                        }
                    }
                }
            }

            Label {
                text: qsTr("Discovered (%1)").arg(mgr.discovered_apps.length)
                font.bold: true
                font.pixelSize: 16
                topPadding: 16
            }

            Label {
                visible: mgr.discovered_apps.length === 0
                text: qsTr("No apps discovered yet. Auto-discovery runs after VM is running.")
                color: palette.placeholderText
            }

            RowLayout {
                spacing: 8
                Button { text: qsTr("+ Add custom .exe") }
                Button { text: qsTr("Refresh discovery"); onClicked: mgr.refresh() }
            }
        }
    }
}
