#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

from gi import require_version
require_version('Gtk', '3.0')
from gi.repository import Gtk
try:
    require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as appIndicator
except Exception:
    require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as appIndicator
require_version('Notify', '0.7')
from gi.repository import Notify
require_version('GdkPixbuf', '2.0')
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.GLib import timeout_add, source_remove, idle_add, unix_signal_add, PRIORITY_HIGH
from sys import exit as sysExit
from webbrowser import open_new as openNewBrowser
from signal import SIGTERM, SIGINT
from os.path import exists as pathExists, join as pathJoin, relpath as relativePath, expanduser
from os import getenv
from daemon import YDDaemon
from tools import copyFile, deleteFile, makeDirs, shortPath, CVal, Config, activateActions, checkAutoStart
from tools import argParse, call, pathExists, LOGGER, _
from datetime import datetime

APP_NAME = 'yandex-disk-indicator'
APP_VER = '1.12.3'
#
COPYRIGHT = 'Copyright ' + '\u00a9' + ' 2013-' + str(datetime.today().year) + ' Sly_tom_cat'
#
LICENSE = """
This program is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see http://www.gnu.org/licenses
"""


class Notification:
    # On-screen notification


    def __init__(self, title):
        # Initialize notification engine
        if not Notify.is_initted():
            Notify.init(APP_NAME)
        self.title = title
        self.note = None


    def send(self, message):
        # global APP_LOGO
        LOGGER.debug(f'Message: {self.title} | {message}')
        if self.note is not None:
            try:
                self.note.close()
            except:
                pass
            self.note = None
        try:                            # Create notification
            self.note = Notify.Notification.new(self.title, message)
            self.note.set_image_from_pixbuf(APP_LOGO)
            self.note.show()              # Display new notification
        except:
            LOGGER.error('Message engine failure')


# ################### Indicator class ################### #
class Indicator(YDDaemon):
    # Yandex.Disk appIndicator class


    # ###### YDDaemon virtual classes/methods implementations
    def error(self, errStr, cfgPath):
        # Error handler GUI implementation
        # it must handle error cases:
        # - yandex-disk is not installed (errStr=='' in that case)
        # - yandex-disk is not configured (errStr!='' in that case)
        # in both cases it show error message and return
        if errStr == '':
            text1 = _('Yandex.Disk Indicator: daemon start failed')
            buttons = Gtk.ButtonsType.OK
            text2 = (_('Yandex.Disk utility is not installed.\n' +
                       'Visit www.yandex.ru, download and install Yandex.Disk daemon.'))
        else:
            text1 = _('Yandex.Disk Indicator: daemon start failed')
            buttons = Gtk.ButtonsType.OK_CANCEL
            text2 = (_('Yandex.Disk daemon failed to start because it is not' +
                       ' configured properly\n\n' + errStr + '\n\n' +
                       '  To configure it up: press OK button.\n  Press Cancel to exit.'))
        dialog = Gtk.MessageDialog(parent=None, flags=0, message_type=Gtk.MessageType.INFO, buttons=buttons, text=text1)
        dialog.format_secondary_text(text2)
        dialog.set_icon(APP_LOGO)
        response = dialog.run()

        if errStr != '' and response == Gtk.ResponseType.OK:  # Launch Set-up utility
            LOGGER.debug('starting configuration utility')
            retCode = call([pathJoin(APP_INST_PATH, 'ya-setup'), cfgPath])
        else:
            retCode = 1
        dialog.destroy()
        return retCode              # 0 when error is not critical or fixed (daemon has been configured via ya-setup)


    def change(self, vals):
        # Implementation of daemon class call-back function
        # NOTE: it is called not from main thread, so it have to add action in main GUI loop queue
        # It handles daemon status changes by updating icon, creating messages and also update
        # status information in menu (status, sizes and list of last synchronized items).
        # It is called when daemon detects any change of its status.
        LOGGER.info(f"{self.ID}Change event: {','.join(['stat' if vals['statchg'] else '', 'size' if vals['szchg'] else '', 'last' if vals['lastchg'] else ''])}")
        def do_change(vals, path):
            # Update information in menu
            self.menu.update(vals, path)
            # Handle daemon status change by icon change
            if vals['status'] != vals['laststatus']:
                LOGGER.info(f"Status: {vals['laststatus']} -> {vals['status']}")
                self.icons.set(vals['status'])               # Update icon
                # Create notifications for status change events
                if APP_CONF['notifications']:
                    if vals['laststatus'] == 'none':       # Daemon has been started
                        self.notify.send(_('Yandex.Disk daemon has been started'))
                    if vals['status'] == 'busy':           # Just entered into 'busy'
                        self.notify.send(_('Synchronization started'))
                    elif vals['status'] == 'idle':         # Just entered into 'idle'
                        if vals['laststatus'] == 'busy':     # ...from 'busy' status
                            self.notify.send(_('Synchronization has been completed'))
                    elif vals['status'] == 'paused':       # Just entered into 'paused'
                        if vals['laststatus'] not in ['none', 'unknown']:  # ...not from 'none'/'unknown' status
                            self.notify.send(_('Synchronization has been paused'))
                    elif vals['status'] == 'none':         # Just entered into 'none' from some another status
                        if vals['laststatus'] != 'unknown':  # ... not from 'unknown'
                            self.notify.send(_('Yandex.Disk daemon has been stopped'))
                    else:                                  # status is 'error' or 'no-net'
                        self.notify.send(_('Synchronization ERROR'))
            # Remember current status (required for Preferences dialog)
            self.currentStatus = vals['status']
        idle_add(do_change, vals, self.config['dir'])


    ### Own classes/methods ###
    def __init__(self, path, ID):
        # Create indicator notification engine
        self.notify = Notification(title=_('Yandex.Disk ') + ID)
        title = _("Yandex.Disk Indicator") + (" "+ID[:-1] if ID != "" else "")
        # Create App Indicator
        id = f'yandex-disk{"-"+ID[:-1] if ID != "" else ""}'
        self.ind = appIndicator.Indicator.new(id, "", appIndicator.IndicatorCategory.APPLICATION_STATUS)
        # Create staff for icons
        self.icons = Icons(title, self.ind.set_icon_full)
        # Setup icons theme
        self.icons.set_theme(APP_CONF['theme'])
        self.ind.set_title(title=title)
        self.ind.set_status(appIndicator.IndicatorStatus.ACTIVE)
        self.menu = self.Menu(self, ID)               # Create menu for daemon
        self.ind.set_menu(self.menu)                  # Attach menu to indicator
        # Initialize Yandex.Disk daemon connection object
        super().__init__(path, ID)
        self.currentStatus = None                     # Current daemon status


    def exit(self):
        def do_exit(self):
            self.icons.close()
            self.menu.destroy()
            self.ind.set_status(appIndicator.IndicatorStatus.PASSIVE)
            LOGGER.debug("Indicator destroyed")
        idle_add(do_exit, self)
        super().exit()


    class Menu(Gtk.Menu):               # Indicator menu

        def __init__(self, daemon, ID):
            self.daemon = daemon                      # Store reference to daemon object for future usage
            self.folder = ''
            super().__init__()                        # Initialize menu
            self.ID = ID
            if self.ID != '':                         # Add addition field in multidaemon mode
                self.yddir = Gtk.MenuItem(label='');  self.yddir.set_sensitive(False);   self.append(self.yddir)
            self.status = Gtk.MenuItem(label='');   self.status.connect("activate", self.showOutput)
            self.append(self.status)
            self.used = Gtk.MenuItem(label='');     self.used.set_sensitive(False)
            self.append(self.used)
            self.free = Gtk.MenuItem(label='');     self.free.set_sensitive(False)
            self.append(self.free)
            self.last = Gtk.MenuItem(label=_('Last synchronized items'))
            self.last.set_sensitive(False)
            self.lastItems = Gtk.Menu()               # Sub-menu: list of last synchronized files/folders
            self.last.set_submenu(self.lastItems)     # Add submenu (empty at the start)
            self.append(self.last)
            self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
            self.daemon_ss = Gtk.MenuItem(label='')         # Start/Stop daemon: Label is depends on current daemon status
            self.daemon_ss.connect("activate", self.startStopDaemon)
            self.append(self.daemon_ss)
            self.open_folder = Gtk.MenuItem(label=_('Open Yandex.Disk Folder'))
            self.open_folder.connect("activate", lambda w: self.openPath(w, self.folder))
            self.append(self.open_folder)
            open_web = Gtk.MenuItem(label=_('Open Yandex.Disk on the web'))
            open_web.connect("activate", self.openInBrowser, _('https://disk.yandex.com'))
            self.append(open_web)
            self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
            self.preferences = Gtk.MenuItem(label=_('Preferences'))
            self.preferences.connect("activate", Preferences)
            self.append(self.preferences)
            open_help = Gtk.MenuItem(label=_('Help'))
            m_help = Gtk.Menu()
            help1 = Gtk.MenuItem(label=_('Yandex.Disk daemon'))
            help1.connect("activate", self.openInBrowser, _('https://yandex.com/support/disk/'))
            m_help.append(help1)
            help2 = Gtk.MenuItem(label=_('Yandex.Disk Indicator'))
            help2.connect("activate", self.openInBrowser, _('https://github.com/slytomcat/yandex-disk-indicator/wiki/Yandex-disk-indicator'))
            m_help.append(help2)
            open_help.set_submenu(m_help)
            self.append(open_help)
            self.about = Gtk.MenuItem(label=_('About'));    self.about.connect("activate", self.openAbout)
            self.append(self.about)
            self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
            close = Gtk.MenuItem(label=_('Quit'))
            close.connect("activate", self.close)
            self.append(close)
            self.show_all()
            # Define user readable statuses dictionary
            self.YD_STATUS = {'idle': _('Synchronized'), 'busy': _('Sync.: '), 'none': _('Not started'),
                              'paused': _('Paused'), 'no_net': _('Not connected'), 'error': _('Error')}


        def update(self, vals, yddir):  # Update information in menu
            self.folder = yddir
            # Update status data on first run or when status has changed
            if vals['statchg'] or vals['laststatus'] == 'unknown':
                self.status.set_label(_('Status: ') + self.YD_STATUS[vals['status']] +
                                      (vals['progress'] if vals['status'] == 'busy' else
                                       ' '.join((':', vals['error'], shortPath(vals['path']))) if vals['status'] == 'error' else ''))
                # Update pseudo-static items on first run or when daemon has stopped or started
                if 'none' in (vals['status'], vals['laststatus']) or vals['laststatus'] == 'unknown':
                    started = vals['status'] != 'none'
                    self.status.set_sensitive(started)
                    # zero-space UTF symbols are used to detect required action without need to compare translated strings
                    self.daemon_ss.set_label(('\u2060' + _('Stop Yandex.Disk daemon')) if started else
                                             ('\u200B' + _('Start Yandex.Disk daemon')))
                    if self.ID != '':                             # Set daemon identity row in multidaemon mode
                        self.yddir.set_label(self.ID + _('  Folder: ') + (shortPath(yddir) if yddir else '< NOT CONFIGURED >'))
                    self.open_folder.set_sensitive(yddir != '')  # Activate Open YDfolder if daemon configured
            # Update sizes data on first run or when size data has changed
            if vals['szchg'] or vals['laststatus'] == 'unknown':
                self.used.set_label(_('Used: ') + vals['used'] + '/' + vals['total'])
                self.free.set_label(_('Free: ') + vals['free'] + _(', trash: ') + vals['trash'])
            # Update last synchronized sub-menu on first run or when last data has changed
            if vals['lastchg'] or vals['laststatus'] == 'unknown':
                # Update last synchronized sub-menu
                self.lastItems.destroy()                      # Disable showing synchronized sub menu while updating it, fix for #197
                self.last.set_sensitive(False)
                self.lastItems = Gtk.Menu()                   # Create new/empty Sub-menu:
                self.last.set_submenu(self.lastItems)
                if len(vals['lastitems']) > 0:
                    for filePath in vals['lastitems']:            # Create new sub-menu items
                        # Create menu label as file path (shorten it down to 50 symbols when path length > 50
                        # symbols), with replaced underscore (to disable menu acceleration feature of GTK menu).
                        widget = Gtk.MenuItem(label=shortPath(filePath))
                        filePath = pathJoin(yddir, filePath)      # Make full path to file
                        if pathExists(filePath):
                            widget.set_sensitive(True)            # If it exists then it can be opened
                            widget.connect("activate", self.openPath, filePath)
                        else:
                            widget.set_sensitive(False)           # Don't allow to open non-existing path
                        self.lastItems.append(widget)
                    # Switch on last items menu sensitivity as lastItems menu has elements
                    self.last.set_sensitive(True)
                LOGGER.debug(f"Sub-menu 'Last synchronized' has {len(self.lastItems)}/{len(vals['lastitems'])} items")
            self.show_all()                                   # Renew menu


        def openAbout(self, widget):            # Show About window
            # global APP_LOGO, APP_INDICATORS
            for i in APP_INDICATORS:
                i.menu.about.set_sensitive(False)             # Disable menu item
            aboutWindow = Gtk.AboutDialog()
            aboutWindow.set_logo(APP_LOGO);   aboutWindow.set_icon(APP_LOGO)
            aboutWindow.set_program_name(_('Yandex.Disk indicator'))
            aboutWindow.set_version(_('Version ') + APP_VER)
            aboutWindow.set_copyright(COPYRIGHT)
            aboutWindow.set_license(LICENSE)
            aboutWindow.set_authors([_('Sly_tom_cat <slytomcat@mail.ru> '),
                                     _('\nSpecial thanks to:'),
                                     _(' - Snow Dimon https://habrahabr.ru/users/Snowdimon/ - author of ya-setup utility'),
                                     _(' - Christiaan Diedericks https://www.thefanclub.co.za/ - author of Grive tools'),
                                     _(' - ryukusu_luminarius <my-faios@ya.ru> - icons designer'),
                                     _(' - metallcorn <metallcorn@jabber.ru> - icons designer'),
                                     _(' - Chibiko <zenogears@jabber.ru> - deb package creation assistance'),
                                     _(' - RingOV <ringov@mail.ru> - localization assistance'),
                                     _(' - GreekLUG team https://launchpad.net/~greeklug - Greek translation'),
                                     _(' - Peyu Yovev <spacy00001@gmail.com> - Bulgarian translation'),
                                     _(' - Eldar Fahreev <fahreeve@yandex.ru> - FM actions for Pantheon-files'),
                                     _(' - Ace Of Snakes <aceofsnakesmain@gmail.com> - optimization of FM actions for Dolphin'),
                                     _(' - Ivan Burmin https://github.com/Zirrald - ya-setup multilingual support'),
                                     _('And to all other people who contributed to this project via'),
                                     _(' - Ubuntu.ru forum http://forum.ubuntu.ru/index.php?topic=241992'),
                                     _(' - github.com https://github.com/slytomcat/yandex-disk-indicator')])
            aboutWindow.set_resizable(False)
            aboutWindow.run()
            aboutWindow.destroy()
            for i in APP_INDICATORS:
                i.menu.about.set_sensitive(True)            # Enable menu item


        def showOutput(self, widget):           # Request for daemon output
            widget.set_sensitive(False)                     # Disable menu item


            def displayOutput(outText, widget):
                # # # NOTE: it is called not from main thread, so it have to add action in main loop queue
                def do_display(outText, widget):
                    # global APP_LOGO
                    statusWindow = Gtk.Dialog(_('Yandex.Disk daemon output message'))
                    statusWindow.set_icon(APP_LOGO)
                    statusWindow.set_border_width(6)
                    statusWindow.add_button(_('Close'), Gtk.ResponseType.CLOSE)
                    textBox = Gtk.TextView()                            # Create text-box to display daemon output
                    # Set output buffer with daemon output in user language
                    textBox.get_buffer().set_text(outText)
                    textBox.set_editable(False)
                    # Put it inside the dialogue content area
                    statusWindow.get_content_area().pack_start(textBox, True, True, 6)
                    statusWindow.show_all();  statusWindow.run();   statusWindow.destroy()
                    widget.set_sensitive(True)                          # Enable menu item
                idle_add(do_display, outText, widget)
            self.daemon.output(lambda t: displayOutput(t, widget))


        def openInBrowser(self, _, url):   # Open URL
            openNewBrowser(url)


        def startStopDaemon(self, widget):      # Start/Stop daemon
            action = widget.get_label()[:1]
            # zero-space UTF symbols are used to detect required action without need to compare translated strings
            if action == '\u200B':    # Start
                self.daemon.start()
            elif action == '\u2060':  # Stop
                self.daemon.stop()


        def openPath(self, _, path):       # Open path
            LOGGER.info(f"Opening {path}")
            if pathExists(path):
                try:
                    call(['xdg-open', path])
                except:
                    LOGGER.error("Opening of {path} failed")


        def close(self, _):                # Quit from indicator
            appExit()


class Timer:                        # Timer implementation (GUI related)
    # Timer class methods:
    # __init__ - initialize the timer object with specified interval and handler. Start it if start value True.
    # start    - Start timer if it is not started yet of do nothing if it is already started.
    # stop     - Stop active timer or do nothing if it is not running.
    # Interface variables:
    # active   - True when timer is currently running, otherwise - False


    def __init__(self, interval, handler, start=True):
        self.interval = interval          # Timer interval (ms)
        self.handler = handler            # Handler function
        self.active = False               # Current activity status
        if start:
            self.start()                    # Start timer if required


    def start(self):       # Start inactive timer or do nothing if it is already active
        if not self.active:
            self.timer = timeout_add(self.interval, self.handler)
            self.active = True


    def stop(self):                     # Stop active timer ar do nothing if it is already stopped
        if self.active:
            source_remove(self.timer)
            self.active = False


class Icons:                        # Icons class for icons handling

    def __init__(self, title: str, set_func):
        self.title = title
        self.set_func = set_func
        self.busy_id = 0
        self.timer = Timer(777, self.animation, start=False)
        self.icons = {}
        self.status = 'none'
        self.ext = "svg"
        self.theme = ""


    def animation(self):          # Changes busy icon by loop (triggered by self.timer)
        # As it called from timer (main GUI thread) there is no need to use idle_add here
        # Calculate next icon number
        self.busy_id = (self.busy_id + 1) % 5   # 5 busy icons shown in endless loop (1-2-3-4-5-1-2-3...)
        # Set next animation icon
        self.set_func(self.icons['busy'][self.busy_id], self.title)
        return True                             # True required to continue triggering by timer


    def set(self, status: str):       # Change indicator icon according to just changed daemon status
        # Set icon according to the current daemon status
        if status == 'busy':            # Just entered into 'busy' status
            self.set_func(self.icons[status][self.busy_id], self.title)
            self.timer.start()     # Start animation timer
        else:
            self.timer.stop()      # Stop animation timer when status is not busy
            self.set_func(self.icons[status], self.title)
        self.status = status


    def set_theme(self, theme: bool):
        # Determine paths to icons according to current theme
        # global APP_INST_PATH, APP_CONF_PATH
        self.theme = 'light' if theme else 'dark'
        # Determine theme from application configuration settings
        default_path = pathJoin(APP_INST_PATH, 'icons', self.theme)
        user_path = pathJoin(APP_CONF_PATH, 'icons', self.theme)
        def set_icon (file_name: str):
            user_icon = pathJoin(user_path, file_name)
            return user_icon if pathExists(user_icon) else pathJoin(default_path, file_name)
        # Set appropriate paths to all status icons
        # Five busy icons are shown in endless loop
        self.icons = {'busy': [set_icon(f"yd-busy{i}.{self.ext}") for i in range(1, 6)]}
        # Other icons is set for all individual status
        for status in ['idle', 'error', 'paused', 'none', 'no_net']:
            self.icons[status] = set_icon(f'yd-pause.{self.ext}' if status in {'paused', 'none', 'no_net'} else f'yd-{status}.{self.ext}')
        # renew icon according the selected theme
        self.set(self.status)
        global APP_LOGO
        APP_LOGO = Pixbuf.new_from_file(set_icon(f"yd-logo.{self.ext}"))
        LOGGER.debug(f"selected icons: {self.icons}")


    def set_type(self, ext: bool):
        self.ext = "png" if ext else "svg"
        self.set_theme(self.theme=='light')


    def close(self):
        self.timer.stop()


# ### Application functions and classes
class Preferences(Gtk.Dialog):
    # Preferences window of application and daemons


    class excludeDirsList(Gtk.Dialog):
        # Excluded dirs dialogue


        def __init__(self, widget, parent, d_config):   # show current list
            self.d_config = d_config
            self.parent = parent
            Gtk.Dialog.__init__(self, title=_('Folders that are excluded from synchronization'),
                                parent=parent, flags=1)
            self.set_icon(APP_LOGO)
            self.set_size_request(400, 300)
            self.add_button(_('Add catalogue'),
                            Gtk.ResponseType.APPLY).connect("clicked", self.addFolder, self)
            self.add_button(_('Remove selected'),
                            Gtk.ResponseType.REJECT).connect("clicked", self.deleteSelected)
            self.add_button(_('Close'),
                            Gtk.ResponseType.CLOSE).connect("clicked", self.exitFromDialog)
            self.ex_list = Gtk.ListStore(bool, str)
            view = Gtk.TreeView(model=self.ex_list)
            render = Gtk.CellRendererToggle()
            render.connect("toggled", self.lineToggled)
            view.append_column(Gtk.TreeViewColumn(" ", render, active=0))
            view.append_column(Gtk.TreeViewColumn(_('Path'), Gtk.CellRendererText(), text=1))
            scroll = Gtk.ScrolledWindow()
            scroll.add(view)
            self.get_content_area().pack_start(scroll, True, True, 6)
            # Populate list with paths from "exclude-dirs" property of daemon configuration
            self.dir_set = list(CVal(self.d_config.get('exclude-dirs', None)))
            for val in self.dir_set:
                self.ex_list.append([False, val])
            # LOGGER.debug(str(self.dir_set))
            self.show_all()


        def exitFromDialog(self, widget):     # Save list from dialogue to "exclude-dirs" property
            if self.d_config.changed:
                eList = CVal()                                      # Store path value from dialogue rows
                for i in self.dir_set:
                    eList.add(i)
                self.d_config['exclude-dirs'] = eList.get()          # Save collected value
            # LOGGER.debug(str(self.dir_set))
            self.destroy()                                        # Close dialogue


        def lineToggled(self, _, path):  # Line click handler, it switch row selection
            self.ex_list[path][0] = not self.ex_list[path][0]


        def deleteSelected(self, _):     # Remove selected rows from list
            list_iter = self.ex_list.get_iter_first()
            while list_iter is not None and self.ex_list.iter_is_valid(list_iter):
                if self.ex_list.get(list_iter, 0)[0]:
                    self.dir_set.remove(self.ex_list.get(list_iter, 1)[0])
                    self.ex_list.remove(list_iter)
                    self.d_config.changed = True
                else:
                    list_iter = self.ex_list.iter_next(list_iter)
            # LOGGER.debug(str(self.dir_set))


        def addFolder(self, widget, parent):  # Add new path to list via FileChooserDialog
            dialog = Gtk.FileChooserDialog(title=_('Select catalogue to add to list'), parent=parent, action=Gtk.FileChooserAction.SELECT_FOLDER)
            dialog.add_button(_('Close'), Gtk.ResponseType.CANCEL)
            dialog.add_button(_('Select'), Gtk.ResponseType.ACCEPT)
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            dialog.set_select_multiple(True)
            rootDir = self.d_config['dir']
            dialog.set_current_folder(rootDir)
            if dialog.run() == Gtk.ResponseType.ACCEPT:
                for path in dialog.get_filenames():
                    if path.startswith(rootDir):
                        path = relativePath(path, start=rootDir)
                        if path not in self.dir_set:
                            self.ex_list.append([False, path])
                            self.dir_set.append(path)
                            self.d_config.changed = True
            dialog.destroy()
            # LOGGER.debug(str(self.dir_set))


    def __init__(self, widget):
        # global config, APP_INDICATORS, APP_LOGO
        # Preferences Window routine
        for i in APP_INDICATORS:
            i.menu.preferences.set_sensitive(False)   # Disable menu items to avoid multi-dialogs creation
        # Create Preferences window
        super().__init__(_('Yandex.Disk-indicator and Yandex.Disks preferences'), flags=1)
        self.set_icon(APP_LOGO)
        self.set_border_width(6)
        self.add_button(_('Close'), Gtk.ResponseType.CLOSE)
        pref_notebook = Gtk.Notebook()              # Create notebook for indicator and daemon options
        self.get_content_area().add(pref_notebook)  # Put it inside the dialogue content area
        # --- Indicator preferences tab ---
        preferencesBox = Gtk.VBox(spacing=4)
        cb = []
        for key, msg in [('autostart', _('Start Yandex.Disk indicator when you start your computer')),
                         ('notifications', _('Show on-screen notifications')),
                         ('theme', _('Prefer light icon theme')),
                         ('type', 'PNG-on/SVG-off'),
                         ('fmextensions', _('Activate file manager extensions'))]:
            cb.append(Gtk.CheckButton(label=msg))
            cb[-1].set_active(APP_CONF[key])
            cb[-1].connect("toggled", self.onButtonToggled, cb[-1], key)
            preferencesBox.add(cb[-1])
        # --- End of Indicator preferences tab --- add it to notebook
        pref_notebook.append_page(preferencesBox, Gtk.Label(label=_('Indicator settings')))
        # Add daemon tabs
        for i in APP_INDICATORS:
            # --- Daemon start options tab ---
            optionsBox = Gtk.VBox(spacing=5)
            key = 'startonstartofindicator'           # Start daemon on indicator start
            cbStOnStart = Gtk.CheckButton(label=_('Start Yandex.Disk daemon %swhen indicator is starting')
                                          % i.ID)
            cbStOnStart.set_tooltip_text(_("When daemon was not started before."))
            cbStOnStart.set_active(i.config[key])
            cbStOnStart.connect("toggled", self.onButtonToggled, cbStOnStart, key, i.config)
            optionsBox.add(cbStOnStart)
            key = 'stoponexitfromindicator'           # Stop daemon on exit
            cbStoOnExit = Gtk.CheckButton(label=_('Stop Yandex.Disk daemon %son closing of indicator') % i.ID)
            cbStoOnExit.set_active(i.config[key])
            cbStoOnExit.connect("toggled", self.onButtonToggled, cbStoOnExit, key, i.config)
            optionsBox.add(cbStoOnExit)
            frame = Gtk.Frame()
            frame.set_label(_("NOTE! You have to reload daemon %sto activate following settings") % i.ID)
            frame.set_border_width(6)
            optionsBox.add(frame)
            framedBox = Gtk.VBox(homogeneous=True, spacing=5)
            frame.add(framedBox)
            key = 'read-only'                         # Option Read-Only    # daemon config
            cbRO = Gtk.CheckButton(label=_('Read-Only: Do not upload locally changed files to Yandex.Disk'))
            cbRO.set_tooltip_text(_("Locally changed files will be renamed if a newer version of this " +
                                    "file appear in Yandex.Disk."))
            cbRO.set_active(i.config[key])
            key = 'overwrite'                         # Option Overwrite    # daemon config
            overwrite = Gtk.CheckButton(label=_('Overwrite locally changed files by files' +
                                          ' from Yandex.Disk (in read-only mode)'))
            overwrite.set_tooltip_text(_("Locally changed files will be overwritten if a newer " +
                                         "version of this file appear in Yandex.Disk."))
            overwrite.set_active(i.config[key])
            overwrite.set_sensitive(i.config['read-only'])
            cbRO.connect("toggled", self.onButtonToggled, cbRO, 'read-only', i.config, overwrite)
            framedBox.add(cbRO)
            overwrite.connect("toggled", self.onButtonToggled, overwrite, key, i.config)
            framedBox.add(overwrite)
            # Exclude folders list
            exListButton = Gtk.Button(label=_('Excluded folders List'))
            exListButton.set_tooltip_text(_("Folders in the list will not be synchronized."))
            exListButton.connect("clicked", self.excludeDirsList, self, i.config)
            framedBox.add(exListButton)
            # --- End of Daemon start options tab --- add it to notebook
            pref_notebook.append_page(optionsBox, Gtk.Label(label=_('Daemon %soptions') % i.ID))
        self.set_resizable(False)
        self.show_all()
        self.run()
        if APP_CONF.changed:
            APP_CONF.save()                             # Save app config
        for i in APP_INDICATORS:
            if i.config.changed:
                i.config.save()                         # Save daemon options in config file
            i.menu.preferences.set_sensitive(True)      # Enable menu items
        self.destroy()


    def onButtonToggled(self, _, button, key, d_config=None, ow=None):
        # Handle clicks on controls
        toggleState = button.get_active()
        LOGGER.debug(f'Togged: {key} val: {str(toggleState)}')
        # Update configurations
        if key in ['read-only', 'overwrite', 'startonstartofindicator', 'stoponexitfromindicator']:
            d_config[key] = toggleState                # Update daemon config
            d_config.changed = True
        else:
            APP_CONF.changed = True                   # Update application config
            APP_CONF[key] = toggleState
        if key == 'theme':
            for i in APP_INDICATORS:                  # Update all APP_INDICATORS' icons
                i.icons.set_theme(toggleState)           # Update icon theme
        elif key == 'type':
            for i in APP_INDICATORS:
                i.icons.set_type(toggleState)
        elif key == 'autostart':
            if toggleState:
                copyFile(APP_AUTOSTART_SRC, APP_AUTOSTART_DST)
            else:
                deleteFile(APP_AUTOSTART_DST)
        elif key == 'fmextensions':
            if not button.get_inconsistent():         # It is a first call
                if not activateActions(toggleState, APP_INST_PATH):
                    toggleState = not toggleState         # When activation/deactivation is not success: revert settings back
                    button.set_inconsistent(True)         # set inconsistent state to detect second call
                    button.set_active(toggleState)        # set check-button to reverted status
                    # set_active will raise again the 'toggled' event
            else:                                     # This is a second call
                button.set_inconsistent(False)        # Just remove inconsistent status
        elif key == 'read-only':
            ow.set_sensitive(toggleState)


def appExit():
    # Exit from application (it closes all APP_INDICATORS)
    # global APP_INDICATORS
    LOGGER.debug("Quit is initialized")
    for i in APP_INDICATORS:
        i.exit()
    idle_add(Gtk.main_quit)

# ##################### MAIN #########################
if __name__ == '__main__':
    # Application constants
    # See APP_NAME and APP_VER in the beginning of the code
    APP_HOME = 'yd-tools'
    APP_CONF_PATH = pathJoin(getenv("HOME"), '.config', APP_HOME)
    APP_INST_PATH = pathJoin('/usr/share', APP_HOME)
    # Define .desktop files locations for indicator auto-start facility
    APP_AUTOSTART_SRC = '/usr/share/applications/Yandex.Disk-indicator.desktop'
    APP_AUTOSTART_DST = expanduser('~/.config/autostart/Yandex.Disk-indicator.desktop')

    # Get command line arguments or their default values
    args = argParse(APP_VER)

    # Set user specified logging level
    LOGGER.setLevel(args.level)

    # Report app version and logging level
    LOGGER.info('%s v.%s', APP_NAME, APP_VER)
    LOGGER.debug('Logging level: %s', str(args.level))

    # Application configuration

    # User configuration is stored in ~/.config/<APP_HOME>/<APP_NAME>.conf file.
    # This file can contain comments (line starts with '#') and config values in
    # form: key=value[,value[,value ...]] where keys and values can be quoted ("...") or not.
    # The following key words are reserved for configuration:
    #   autostart, notifications, theme, fmextensions and daemons.

    # The dictionary 'config' stores the config settings for usage in code. Its values are saved to
    # config file on exit from the Menu.Preferences dialogue or when there is no configuration file
    # when application starts.

    # Note that daemon settings ('dir', 'read-only', 'overwrite' and 'exclude_dir') are stored
    # in ~/.config/yandex-disk/config.cfg file. They are read in YDDaemon.__init__() method
    # (in dictionary YDDaemon.config). Their values are saved to daemon config file also
    # on exit from Menu.Preferences dialogue.

    # Additionally 'startonstartofindicator' and 'stoponexitfromindicator' values are added into daemon
    # configuration file to provide the functionality of obsolete 'startonstart' and 'stoponexit'
    # values for each daemon individually.

    APP_CONF = Config(pathJoin(APP_CONF_PATH, APP_NAME + '.conf'))
    # Read some settings to variables, set default values and update some values
    APP_CONF['autostart'] = checkAutoStart(APP_AUTOSTART_DST)
    # Setup on-screen notification settings from config value
    APP_CONF.setdefault('notifications', True)
    APP_CONF.setdefault('theme', False)
    APP_CONF.setdefault('type', False)
    APP_CONF.setdefault('fmextensions', True)
    APP_CONF.setdefault('daemons', '~/.config/yandex-disk/config.cfg')
    # Is it a first run?
    if not APP_CONF.readSuccess:
        LOGGER.info('No config, probably it is a first run.')
        # Create application config folders in ~/.config
        try:
            makeDirs(APP_CONF_PATH)
            makeDirs(pathJoin(APP_CONF_PATH, 'icons/light'))
            makeDirs(pathJoin(APP_CONF_PATH, 'icons/dark'))
            # Copy icon themes readme to user config catalogue
            copyFile(pathJoin(APP_INST_PATH, 'icons/readme'), pathJoin(APP_CONF_PATH, 'icons/readme'))
        except:
            sysExit(_('Can\'t create configuration files in %s') % APP_CONF_PATH)
        # Activate indicator automatic start on system start-up
        if not pathExists(APP_AUTOSTART_DST):
            try:
                makeDirs(expanduser('~/.config/autostart'))
                copyFile(APP_AUTOSTART_SRC, APP_AUTOSTART_DST)
                APP_CONF['autostart'] = True
            except:
                LOGGER.error('Can\'t activate indicator automatic start on system start-up')

        # Activate FM actions according to config (as it is first run)
        activateActions(APP_CONF['fmextensions'], APP_INST_PATH)
        # Default settings should be saved (later)
        APP_CONF.changed = True

    # Add new daemon if it is not in current list
    daemons = [expanduser(d) for d in CVal(APP_CONF['daemons'])]
    if args.cfg:
        args.cfg = expanduser(args.cfg)
        if args.cfg not in daemons:
            daemons.append(args.cfg)
            APP_CONF.changed = True
    # Remove daemon if it is in the current list
    if args.rcfg:
        args.rcfg = expanduser(args.rcfg)
        if args.rcfg in daemons:
            daemons.remove(args.rcfg)
            APP_CONF.changed = True
    # Check that at least one daemon is in the daemons list
    if not daemons:
        sysExit(_('No daemons specified.\nCheck correctness of -r and -c options.'))
    # Update config if daemons list has been changed
    if APP_CONF.changed:
        APP_CONF['daemons'] = CVal(daemons).get()
        # Update configuration file
        APP_CONF.save()

    # Make indicator objects for each daemon in daemons list
    APP_INDICATORS = []
    for dm in daemons:
        APP_INDICATORS.append(Indicator(dm, _('#%d ') % len(APP_INDICATORS) if len(daemons) > 1 else ''))

    # Register the SIGINT/SIGTERM handler for graceful exit when indicator is killed
    unix_signal_add(PRIORITY_HIGH, SIGINT, appExit)
    unix_signal_add(PRIORITY_HIGH, SIGTERM, appExit)
    # Start GTK Main loop
    Gtk.main()
