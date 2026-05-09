// CrossDesk GNOME Shell extension — tray indicator + quick launcher.
//
// GNOME Shell doesn't render StatusNotifierItem natively, so we ship
// our own indicator that calls into ~/.local/bin/crossdesk for
// state. Communication is via subprocess of the `crossdesk` CLI rather
// than gRPC because GJS has no tonic equivalent and the CLI surface
// is stable.
//
// End-to-end testing requires GNOME Shell 45+ on Linux. The Mac dev
// loop only validates JS syntax via cargo check producing the
// extension bundle as a static asset.

import GObject from 'gi://GObject';
import St from 'gi://St';
import GLib from 'gi://GLib';

import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const CrossDeskIndicator = GObject.registerClass(
class CrossDeskIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'CrossDesk');

        this.add_child(new St.Icon({
            icon_name: 'crossdesk',
            style_class: 'system-status-icon',
        }));

        this._refreshTimer = null;
        this._buildMenu();
        this._refresh();
    }

    _buildMenu() {
        this.menu.removeAll();

        let header = new PopupMenu.PopupMenuItem('CrossDesk', { reactive: false });
        header.label.style = 'font-weight: bold;';
        this.menu.addMenuItem(header);

        this._statusItem = new PopupMenu.PopupMenuItem('Status: …', { reactive: false });
        this.menu.addMenuItem(this._statusItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Curated launchers — populated by _refresh.
        this._appsSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._appsSection);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        let openManager = new PopupMenu.PopupMenuItem('Open Manager');
        openManager.connect('activate', () => GLib.spawn_command_line_async('crossdesk-gui'));
        this.menu.addMenuItem(openManager);

        let suspend = new PopupMenu.PopupMenuItem('Suspend VM');
        suspend.connect('activate', () => GLib.spawn_command_line_async('crossdesk vm suspend'));
        this.menu.addMenuItem(suspend);
    }

    _refresh() {
        try {
            const [, out, , status] = GLib.spawn_command_line_sync('crossdesk doctor --quiet --status-only');
            if (status === 0 && out) {
                const text = new TextDecoder().decode(out).trim();
                this._statusItem.label.text = `Status: ${text}`;
            }
        } catch (e) {
            this._statusItem.label.text = 'Status: not connected';
        }
        // Populate apps from `crossdesk launch --list`. Phase 7 stub
        // returns canned list; Phase 8 wires the real catalog.
        this._appsSection.removeAll();
        ['Notepad', 'Calculator', 'Word', 'Excel'].forEach(app => {
            let item = new PopupMenu.PopupMenuItem(app);
            item.connect('activate', () => {
                GLib.spawn_command_line_async(`crossdesk launch ${app.toLowerCase()}`);
            });
            this._appsSection.addMenuItem(item);
        });
        this._refreshTimer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 30, () => {
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    destroy() {
        if (this._refreshTimer !== null) {
            GLib.source_remove(this._refreshTimer);
            this._refreshTimer = null;
        }
        super.destroy();
    }
});

export default class CrossDeskExtension extends Extension {
    enable() {
        this._indicator = new CrossDeskIndicator();
        // Status area placement: 'right' next to other system indicators.
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
