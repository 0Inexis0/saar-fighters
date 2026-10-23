import QtQuick
import QtQuick.Layouts
import QtQml.Models
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.taskmanager as TaskManager

PlasmoidItem {
    id: root
    preferredRepresentation: fullRepresentation
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    TaskManager.TasksModel {
        id: tasks
        groupMode: TaskManager.TasksModel.GroupDisabled
    }
    Instantiator {
        id: windows
        model: tasks
        delegate: QtObject {
            property string appId: model.AppId
            property int row: index
        }
    }
    function showHome() {
        // Activate via Plasma's task model: normal applications cannot bypass
        // Wayland's focus protection merely by raising an existing window.
        for (let i = 0; i < windows.count; ++i) {
            const window = windows.objectAt(i);
            if (window && (window.appId.replace(/\.desktop$/, "") === "de.saarfighters.Home" || window.appId === "saar-home")) {
                tasks.requestActivate(tasks.index(window.row, 0));
                return;
            }
        }
        launcher.connectSource("/usr/local/bin/saar-home");
    }
    Plasma5Support.DataSource {
        id: launcher
        engine: "executable"
        onNewData: function(source, data) { disconnectSource(source); }
    }
    fullRepresentation: PlasmaComponents.Button {
        id: homeButton
        text: "Startseite"
        hoverEnabled: true
        background: Rectangle {
            y: -6
            width: homeButton.width
            height: homeButton.height + 12
            radius: 8
            color: homeButton.down ? "#616347" : (homeButton.hovered || homeButton.activeFocus ? "#454a36" : "#303329")
        }
        contentItem: Item {
            Image {
                anchors.centerIn: parent
                source: "file:///opt/saar-fighters/app/assets/home.svg"
                sourceSize.width: 32
                sourceSize.height: 32
                width: 32
                height: 32
            }
        }
        padding: 6
        Layout.minimumWidth: 64
        Layout.preferredWidth: 64
        Layout.maximumWidth: 64
        PlasmaComponents.ToolTip.visible: hovered
        PlasmaComponents.ToolTip.text: "Startseite"
        onClicked: root.showHome()
        Accessible.name: "Zur Saar-Fighters Startseite"
    }
}
