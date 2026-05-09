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

        // Sidebar
        Rectangle {
            id: sidebar
            Layout.preferredWidth: 180
            Layout.fillHeight: true
            color: palette.alternateBase

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 4

                Repeater {
                    model: [
                        { id: "dashboard", label: qsTr("Dashboard"), icon: "📊" },
                        { id: "apps",      label: qsTr("Apps"),      icon: "🪟" },
                        { id: "storage",   label: qsTr("Storage"),   icon: "💾" },
                        { id: "lifecycle", label: qsTr("Lifecycle"), icon: "⏻" },
                        { id: "diagnose",  label: qsTr("Diagnose"),  icon: "🩺" },
                        { id: "logs",      label: qsTr("Logs"),      icon: "📜" },
                        { id: "settings",  label: qsTr("Settings"),  icon: "⚙" },
                        { id: "about",     label: qsTr("About"),     icon: "ℹ" },
                    ]

                    delegate: Button {
                        Layout.fillWidth: true
                        flat: true
                        checkable: true
                        checked: stack.currentItem && stack.currentItem.paneId === modelData.id
                        text: modelData.icon + "  " + modelData.label
                        onClicked: stack.replace(paneSource(modelData.id))
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // Main pane
        StackView {
            id: stack
            Layout.fillWidth: true
            Layout.fillHeight: true
            initialItem: "qrc:/qt/qml/com/crossdesk/gui/qml/manager/Dashboard.qml"
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

    // Expose mgr to the loaded panes via a global property the panes
    // bind through `Manager.mgr`.
    property alias mgrInstance: mgr
}
