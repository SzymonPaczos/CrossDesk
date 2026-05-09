import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import com.crossdesk.gui

Item {
    id: diagnose
    property string paneId: "diagnose"

    ManagerState { id: mgr }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: width

        ColumnLayout {
            width: diagnose.width - 32
            spacing: 16

            Frame {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Label {
                        text: qsTr("Pre-flight check")
                        font.bold: true
                    }
                    Repeater {
                        model: mgr.diagnostics
                        delegate: RowLayout {
                            spacing: 8
                            readonly property var parts: modelData.split("|")
                            readonly property string status: parts[0]
                            readonly property string checkName: parts[1]
                            readonly property string message: parts[2]

                            Label {
                                text: glyphFor(status)
                                font.pixelSize: 14
                            }
                            Label {
                                text: checkName
                                Layout.preferredWidth: 130
                                font.family: "monospace"
                            }
                            Label {
                                text: status
                                Layout.preferredWidth: 60
                                color: colorFor(status)
                            }
                            Label {
                                text: message
                                color: palette.placeholderText
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            RowLayout {
                spacing: 8
                Button { text: qsTr("Re-run"); onClicked: mgr.run_diagnostics() }
                Button { text: qsTr("Export diagnostic bundle") }
            }
        }
    }

    function glyphFor(status) {
        switch (status) {
            case "ok":   return "✓";
            case "warn": return "!";
            case "fail": return "✗";
        }
        return "?";
    }

    function colorFor(status) {
        switch (status) {
            case "ok":   return "#3c763d";
            case "warn": return "#8a6d3b";
            case "fail": return "#a94442";
        }
        return palette.placeholderText;
    }
}
