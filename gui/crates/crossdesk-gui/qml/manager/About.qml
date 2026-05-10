import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: about
    property string paneId: "about"

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
                text: qsTr("About")
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
                width: about.width
                Layout.margins: 24
                spacing: 16

                // Hero card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: heroContent.implicitHeight + 28

                    ColumnLayout {
                        id: heroContent
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 16
                        spacing: 16

                        // Hero row: logo + name
                        RowLayout {
                            spacing: 14

                            Rectangle {
                                width: 56
                                height: 56
                                radius: 12
                                color: Qt.rgba(palette.mid.r, palette.mid.g, palette.mid.b, 0.5)

                                Item {
                                    anchors.centerIn: parent
                                    width: 48
                                    height: 48

                                    // CrossDesk logo — two overlapping window rectangles
                                    Rectangle {
                                        x: 4; y: 6
                                        width: 28; height: 22
                                        radius: 3
                                        color: palette.highlight
                                    }
                                    Rectangle {
                                        x: 16; y: 20
                                        width: 28; height: 22
                                        radius: 3
                                        color: palette.text
                                        opacity: 0.85
                                    }
                                }
                            }

                            ColumnLayout {
                                spacing: 2
                                Label {
                                    text: "CrossDesk"
                                    font.pixelSize: 18
                                    font.weight: Font.DemiBold
                                    color: palette.text
                                    font.letterSpacing: -0.2
                                }
                                Label {
                                    text: qsTr("Windows apps as native Wayland/X11 windows.")
                                    font.pixelSize: 12
                                    color: palette.placeholderText
                                }
                            }
                        }

                        // Separator
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: palette.mid
                            opacity: 0.6
                        }

                        // Metadata grid
                        GridLayout {
                            columns: 3
                            rowSpacing: 12
                            columnSpacing: 32

                            // Version
                            ColumnLayout {
                                spacing: 2
                                Label {
                                    text: qsTr("VERSION")
                                    font.pixelSize: 10
                                    color: palette.placeholderText
                                    font.letterSpacing: 0.4
                                }
                                Label {
                                    text: "0.1.0 (pre-release)"
                                    font.family: "monospace"
                                    font.pixelSize: 12
                                }
                            }

                            // License
                            ColumnLayout {
                                spacing: 2
                                Label {
                                    text: qsTr("LICENSE")
                                    font.pixelSize: 10
                                    color: palette.placeholderText
                                    font.letterSpacing: 0.4
                                }
                                Label {
                                    text: "GPL-3.0-or-later"
                                    font.family: "monospace"
                                    font.pixelSize: 12
                                }
                            }

                            // Links
                            ColumnLayout {
                                spacing: 2
                                Label {
                                    text: qsTr("LINKS")
                                    font.pixelSize: 10
                                    color: palette.placeholderText
                                    font.letterSpacing: 0.4
                                }
                                Label {
                                    textFormat: Text.RichText
                                    onLinkActivated: (link) => Qt.openUrlExternally(link)
                                    text: '<a href="https://github.com/SzymonPaczos/CrossDesk">GitHub</a> · ' +
                                          '<a href="https://github.com/SzymonPaczos/CrossDesk/blob/main/docs/GOALS.md">Vision</a> · ' +
                                          '<a href="https://github.com/SzymonPaczos/CrossDesk/blob/main/docs/THREAT_MODEL.md">Threat model</a>'
                                    font.pixelSize: 12
                                }
                            }
                        }
                    }
                }

                // Easter egg card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    color: palette.base
                    border.color: palette.mid
                    border.width: 1
                    radius: 6
                    implicitHeight: easterHeader.height + easterBody.implicitHeight + 28

                    Rectangle {
                        id: easterHeader
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
                            text: qsTr("Phase 4 SPOF")
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ColumnLayout {
                        id: easterBody
                        anchors.top: easterHeader.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 14
                        spacing: 0

                        Label {
                            // Easter egg: per ROADMAP.md
                            text: "kolejność i idempotencja eventów (CREATED przed FOCUS_GAINED, brak zgubionego DESTROYED) — rozjazd stanu HWND↔Linux window = ghost windows lub orphaned process"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            color: palette.placeholderText
                            font.pixelSize: 12
                        }
                    }
                }

                Item { height: 8 }
            }
        }
    }
}
