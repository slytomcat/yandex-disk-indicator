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
from os import getenv, getpid, geteuid
from daemon import YDDaemon
from tools import copyFile, deleteFile, makeDirs, shortPath, CVal, Config, activateActions, checkAutoStart
from tools import setProcName, argParse, check_output, call, pathExists, LOGGER, _
from datetime import datetime

APPNAME = 'yandex-disk-indicator'
APPVER = '1.12.1'
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
            Notify.init(APPNAME)
        self.title = title
        self.note = None


    def send(self, messg):
        # global APPLOGO
        LOGGER.debug('Message: %s | %s', self.title, messg)
        if self.note is not None:
            try:
                self.note.close()
            except:
                pass
            self.note = None
        try:                            # Create notification
            self.note = Notify.Notification.new(self.title, messg)
            self.note.set_image_from_pixbuf(APPLOGO)
            self.note.show()              # Display new notification
        except:
            LOGGER.error('Message engine failure')


# ################### Indicator class ################### #
class Indicator(YDDaemon):
    # Yandex.Disk appIndicator class


    # ###### YDDaemon virtual classes/methods implementations
    def error(self, errStr, cfgPath):
        # Error handler GUI implementation
        # it must handle two types of error cases:
        # - yandex-disk is not installed (errStr=='' in that case) - just show error message and return
        # - yandex-disk is not configured (errStr!='' in that case) - suggest to configure it and run ya-setup if needed
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
        dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, buttons, text1)
        dialog.format_secondary_text(text2)
        dialog.set_icon(APPLOGO)
        response = dialog.run()

        if errStr != '' and response == Gtk.ResponseType.OK:  # Launch Set-up utility
            LOGGER.debug('starting configuration utility')
            retCode = call([pathJoin(APPINSTPATH, 'ya-setup'), cfgPath])
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

        LOGGER.info('%sChange event: %s', self.ID, ','.join(['stat' if vals['statchg'] else '',
                                                             'size' if vals['szchg'] else '',
                                                             'last' if vals['lastchg'] else '']))

        def do_change(vals, path):
            # Update information in menu
            self.menu.update(vals, path)
            # Handle daemon status change by icon change
            if vals['status'] != vals['laststatus']:
                LOGGER.info('Status: %s ->  %s', vals['laststatus'], vals['status'])
                self.updateIcon(vals['status'])          # Update icon
                # Create notifications for status change events
                if APPCONF['notifications']:
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
        # Setup icons theme
        self.setIconTheme(APPCONF['theme'])
        # Create staff for icon animation support (don't start it here)

        self._seqNum = 2  # Number current busy icon

        def iconAnimation():          # Changes busy icon by loop (triggered by self.timer)
            # As it called from timer (main GUI thread) there is no need to use idle_add here
            # Set next animation icon
            self.ind.set_icon_full(pathJoin(self.themePath, 'yd-busy' + str(self._seqNum) + '.png'), '')
            # Calculate next icon number
            self._seqNum = self._seqNum % 5 + 1   # 5 icon numbers in loop (1-2-3-4-5-1-2-3...)
            return True                           # True required to continue triggering by timer

        self.iconTimer = self.Timer(777, iconAnimation, start=False)
        # Create App Indicator
        self.ind = appIndicator.Indicator.new(
            "yandex-disk%s" % ("-"+ID[1: -1] if ID != "" else ""),
            self.icon['paused'],
            appIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_title(title=_("Yandex.Disk Indicator") + (" "+ID[:-1] if ID != "" else ""))
        self.ind.set_status(appIndicator.IndicatorStatus.ACTIVE)
        self.menu = self.Menu(self, ID)               # Create menu for daemon
        self.ind.set_menu(self.menu)                  # Attach menu to indicator
        # Initialize Yandex.Disk daemon connection object
        super().__init__(path, ID)
        self.currentStatus = None                 # Current daemon status


    def exit(self):
        def do_exit(self):
            self.menu.destroy()
            self.ind.set_status(appIndicator.IndicatorStatus.PASSIVE)
            LOGGER.debug("Indicator destroyed")
        idle_add(do_exit, self)
        super().exit()


    def setIconTheme(self, theme):
        # Determine paths to icons according to current theme
        # global APPINSTPATH, APPCONFPATH
        theme = 'light' if theme else 'dark'
        # Determine theme from application configuration settings
        defaultPath = pathJoin(APPINSTPATH, 'icons', theme)
        userPath = pathJoin(APPCONFPATH, 'icons', theme)
        # Set appropriate paths to all status icons
        self.icon = {}
        for status in ['idle', 'error', 'paused', 'none', 'no_net', 'busy']:
            name = ('yd-ind-pause.png' if status in {'paused', 'none', 'no_net'} else
                    'yd-busy1.png' if status == 'busy' else
                    'yd-ind-' + status + '.png')
            userIcon = pathJoin(userPath, name)
            self.icon[status] = userIcon if pathExists(userIcon) else pathJoin(defaultPath, name)
            # userIcon corresponds to busy icon on exit from this loop
        # Set theme paths according to existence of first busy icon
        self.themePath = userPath if pathExists(userIcon) else defaultPath


    def updateIcon(self, status):       # Change indicator icon according to just changed daemon status
        # Set icon according to the current daemon status
        self.ind.set_icon_full(self.icon[status], '')
        # Handle animation
        if status == 'busy':        # Just entered into 'busy' status
            self._seqNum = 2          # Next busy icon number for animation
            self.iconTimer.start()    # Start animation timer
        else:
            self.iconTimer.stop()     # Stop animation timer when status is not busy


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
            help2.connect("activate", self.openInBrowser,
                          _('https://github.com/slytomcat/yandex-disk-indicator/wiki/Yandex-disk-indicator'))
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
                self.lastItems.destroy()                      # Disable showing synchronized sub menu while updating it - temp fix for #197
                self.lastItems = Gtk.Menu()                   # Create new/empty Sub-menu:
                for filePath in vals['lastitems']:            # Create new sub-menu items
                    # Create menu label as file path (shorten it down to 50 symbols when path length > 50
                    # symbols), with replaced underscore (to disable menu acceleration feature of GTK menu).
                    widget = Gtk.MenuItem.new_with_label(shortPath(filePath))
                    filePath = pathJoin(yddir, filePath)        # Make full path to file
                    if pathExists(filePath):
                        widget.set_sensitive(True)                # If it exists then it can be opened
                        widget.connect("activate", self.openPath, filePath)
                    else:
                        widget.set_sensitive(False)               # Don't allow to open non-existing path
                    self.lastItems.append(widget)
                self.last.set_submenu(self.lastItems)
                # Switch off last items menu sensitivity if no items in list
                self.last.set_sensitive(vals['lastitems'])
                LOGGER.debug("Sub-menu 'Last synchronized' has %s items", str(len(vals['lastitems'])))

            self.show_all()                                 # Renew menu


        def openAbout(self, widget):            # Show About window
            # global APPLOGO, APPINDICATORS
            for i in APPINDICATORS:
                i.menu.about.set_sensitive(False)           # Disable menu item
            aboutWindow = Gtk.AboutDialog()
            aboutWindow.set_logo(APPLOGO);   aboutWindow.set_icon(APPLOGO)
            aboutWindow.set_program_name(_('Yandex.Disk indicator'))
            aboutWindow.set_version(_('Version ') + APPVER)
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
            for i in APPINDICATORS:
                i.menu.about.set_sensitive(True)            # Enable menu item


        def showOutput(self, widget):           # Request for daemon output
            widget.set_sensitive(False)                         # Disable menu item


            def displayOutput(outText, widget):
                # # # NOTE: it is called not from main thread, so it have to add action in main loop queue
                def do_display(outText, widget):
                    # global APPLOGO
                    statusWindow = Gtk.Dialog(_('Yandex.Disk daemon output message'))
                    statusWindow.set_icon(APPLOGO)
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
            # zero-space UTF symbols are used to detect requered action without need to compare translated strings
            if action == '\u200B':    # Start
                self.daemon.start()
            elif action == '\u2060':  # Stop
                self.daemon.stop()


        def openPath(self, _, path):       # Open path
            LOGGER.info("Opening '%s'", path)
            if pathExists(path):
                try:
                    call(['xdg-open', path])
                except:
                    LOGGER.error("Start of '%s' failed", path)


        def close(self, _):                # Quit from indicator
            appExit()


    class Timer:                        # Timer implementation (GUI related)
        # Timer class methods:

        # __init__ - initialize the timer object with specified interval and handler. Start it if start value True.
        # start    - Start timer if it is not started yet.
        # stop     - Stop running timer or do nothing if it is not running.

        # Interface variables:

        # active   - True when timer is currently running, otherwise - False

        def __init__(self, interval, handler, start=True):
            self.interval = interval          # Timer interval (ms)
            self.handler = handler            # Handler function
            self.active = False               # Current activity status
            if start:
                self.start()                    # Start timer if required


        def start(self):       # Start inactive timer or update if it is active
            if not self.active:
                self.timer = timeout_add(self.interval, self.handler)
                self.active = True
                # LOGGER.debug('timer started %s %s', self.timer, interval)


        def stop(self):                     # Stop active timer
            if self.active:
                # LOGGER.debug('timer to stop %s', self.timer)
                source_remove(self.timer)
                self.active = False


# ### Application functions and classes
class Preferences(Gtk.Dialog):
    # Preferences window of application and daemons


    class excludeDirsList(Gtk.Dialog):
        # Excluded dirs dialogue


        def __init__(self, widget, parent, dcofig):   # show current list
            self.dconfig = dcofig
            self.parent = parent
            Gtk.Dialog.__init__(self, title=_('Folders that are excluded from synchronization'),
                                parent=parent, flags=1)
            self.set_icon(APPLOGO)
            self.set_size_request(400, 300)
            self.add_button(_('Add catalogue'),
                            Gtk.ResponseType.APPLY).connect("clicked", self.addFolder, self)
            self.add_button(_('Remove selected'),
                            Gtk.ResponseType.REJECT).connect("clicked", self.deleteSelected)
            self.add_button(_('Close'),
                            Gtk.ResponseType.CLOSE).connect("clicked", self.exitFromDialog)
            self.exList = Gtk.ListStore(bool, str)
            view = Gtk.TreeView(model=self.exList)
            render = Gtk.CellRendererToggle()
            render.connect("toggled", self.lineToggled)
            view.append_column(Gtk.TreeViewColumn(" ", render, active=0))
            view.append_column(Gtk.TreeViewColumn(_('Path'), Gtk.CellRendererText(), text=1))
            scroll = Gtk.ScrolledWindow()
            scroll.add_with_viewport(view)
            self.get_content_area().pack_start(scroll, True, True, 6)
            # Populate list with paths from "exclude-dirs" property of daemon configuration
            self.dirset = list(CVal(self.dconfig.get('exclude-dirs', None)))
            for val in self.dirset:
                self.exList.append([False, val])
            # LOGGER.debug(str(self.dirset))
            self.show_all()


        def exitFromDialog(self, widget):     # Save list from dialogue to "exclude-dirs" property
            if self.dconfig.changed:
                eList = CVal()                                      # Store path value from dialogue rows
                for i in self.dirset:
                    eList.add(i)
                self.dconfig['exclude-dirs'] = eList.get()          # Save collected value
            # LOGGER.debug(str(self.dirset))
            self.destroy()                                        # Close dialogue


        def lineToggled(self, _, path):  # Line click handler, it switch row selection
            self.exList[path][0] = not self.exList[path][0]


        def deleteSelected(self, _):     # Remove selected rows from list
            listIiter = self.exList.get_iter_first()
            while listIiter is not None and self.exList.iter_is_valid(listIiter):
                if self.exList.get(listIiter, 0)[0]:
                    self.dirset.remove(self.exList.get(listIiter, 1)[0])
                    self.exList.remove(listIiter)
                    self.dconfig.changed = True
                else:
                    listIiter = self.exList.iter_next(listIiter)
            # LOGGER.debug(str(self.dirset))


        def addFolder(self, widget, parent):  # Add new path to list via FileChooserDialog
            dialog = Gtk.FileChooserDialog(_('Select catalogue to add to list'), parent, Gtk.FileChooserAction.SELECT_FOLDER,
                                           (_('Close'), Gtk.ResponseType.CANCEL, _('Select'), Gtk.ResponseType.ACCEPT))
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            dialog.set_select_multiple(True)
            rootDir = self.dconfig['dir']
            dialog.set_current_folder(rootDir)
            if dialog.run() == Gtk.ResponseType.ACCEPT:
                for path in dialog.get_filenames():
                    if path.startswith(rootDir):
                        path = relativePath(path, start=rootDir)
                        if path not in self.dirset:
                            self.exList.append([False, path])
                            self.dirset.append(path)
                            self.dconfig.changed = True
            dialog.destroy()
            # LOGGER.debug(str(self.dirset))


    def __init__(self, widget):
        # global config, APPINDICATORS, APPLOGO
        # Preferences Window routine
        for i in APPINDICATORS:
            i.menu.preferences.set_sensitive(False)   # Disable menu items to avoid multi-dialogs creation
        # Create Preferences window
        super().__init__(_('Yandex.Disk-indicator and Yandex.Disks preferences'), flags=1)
        self.set_icon(APPLOGO)
        self.set_border_width(6)
        self.add_button(_('Close'), Gtk.ResponseType.CLOSE)
        pref_notebook = Gtk.Notebook()              # Create notebook for indicator and daemon options
        self.get_content_area().add(pref_notebook)  # Put it inside the dialogue content area
        # --- Indicator preferences tab ---
        preferencesBox = Gtk.VBox(spacing=5)
        cb = []
        for key, msg in [('autostart', _('Start Yandex.Disk indicator when you start your computer')),
                         ('notifications', _('Show on-screen notifications')),
                         ('theme', _('Prefer light icon theme')),
                         ('fmextensions', _('Activate file manager extensions'))]:
            cb.append(Gtk.CheckButton(label=msg))
            cb[-1].set_active(APPCONF[key])
            cb[-1].connect("toggled", self.onButtonToggled, cb[-1], key)
            preferencesBox.add(cb[-1])
        # --- End of Indicator preferences tab --- add it to notebook
        pref_notebook.append_page(preferencesBox, Gtk.Label(label=_('Indicator settings')))
        # Add daemos tabs
        for i in APPINDICATORS:
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
            # Excude folders list
            exListButton = Gtk.Button(label=_('Excluded folders List'))
            exListButton.set_tooltip_text(_("Folders in the list will not be synchronized."))
            exListButton.connect("clicked", self.excludeDirsList, self, i.config)
            framedBox.add(exListButton)
            # --- End of Daemon start options tab --- add it to notebook
            pref_notebook.append_page(optionsBox, Gtk.Label(label=_('Daemon %soptions') % i.ID))
        self.set_resizable(False)
        self.show_all()
        self.run()
        if APPCONF.changed:
            APPCONF.save()                              # Save app config
        for i in APPINDICATORS:
            if i.config.changed:
                i.config.save()                         # Save daemon options in config file
            i.menu.preferences.set_sensitive(True)      # Enable menu items
        self.destroy()


    def onButtonToggled(self, _, button, key, dconfig=None, ow=None):
        # Handle clicks on controls
        toggleState = button.get_active()
        LOGGER.debug('Togged: %s  val: %s', key, str(toggleState))
        # Update configurations
        if key in ['read-only', 'overwrite', 'startonstartofindicator', 'stoponexitfromindicator']:
            dconfig[key] = toggleState                # Update daemon config
            dconfig.changed = True
        else:
            APPCONF.changed = True                     # Update application config
            APPCONF[key] = toggleState
        if key == 'theme':
            for i in APPINDICATORS:                    # Update all APPINDICATORS' icons
                i.setIconTheme(toggleState)           # Update icon theme
                i.updateIcon(i.currentStatus)         # Update current icon
        elif key == 'autostart':
            if toggleState:
                copyFile(APPAUTOSTARTSRC, APPAUTOSTARTDST)
            else:
                deleteFile(APPAUTOSTARTDST)
        elif key == 'fmextensions':
            if not button.get_inconsistent():         # It is a first call
                if not activateActions(toggleState, APPINSTPATH):
                    toggleState = not toggleState         # When activation/deactivation is not success: revert settings back
                    button.set_inconsistent(True)         # set inconsistent state to detect second call
                    button.set_active(toggleState)        # set check-button to reverted status
                    # set_active will raise again the 'toggled' event
            else:                                     # This is a second call
                button.set_inconsistent(False)          # Just remove inconsistent status
        elif key == 'read-only':
            ow.set_sensitive(toggleState)


def appExit():
    # Exit from application (it closes all APPINDICATORS)
    # global APPINDICATORS
    LOGGER.debug("Quit is initialized")
    for i in APPINDICATORS:
        i.exit()
    idle_add(Gtk.main_quit)

# ##################### MAIN #########################
if __name__ == '__main__':
    # Application constants
    # See APPNAME and APPVER in the beginnig of the code
    APPHOME = 'yd-tools'
    APPINSTPATH = pathJoin('/usr/share', APPHOME)
    APPLOGO = Pixbuf.new_from_file(pathJoin(APPINSTPATH, 'icons/yd-128.png'))
    APPCONFPATH = pathJoin(getenv("HOME"), '.config', APPHOME)
    # Define .desktop files locations for indicator auto-start facility
    APPAUTOSTARTSRC = '/usr/share/applications/Yandex.Disk-indicator.desktop'
    APPAUTOSTARTDST = expanduser('~/.config/autostart/Yandex.Disk-indicator.desktop')

    # Get command line arguments or their default values
    args = argParse(APPVER)

    # Set user specified logging level
    LOGGER.setLevel(args.level)

    # Report app version and logging level
    LOGGER.info('%s v.%s', APPNAME, APPVER)
    LOGGER.debug('Logging level: %s', str(args.level))

    # Application configuration

    # User configuration is stored in ~/.config/<APPHOME>/<APPNAME>.conf file.
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

    APPCONF = Config(pathJoin(APPCONFPATH, APPNAME + '.conf'))
    # Read some settings to variables, set default values and update some values
    APPCONF['autostart'] = checkAutoStart(APPAUTOSTARTDST)
    # Setup on-screen notification settings from config value
    APPCONF.setdefault('notifications', True)
    APPCONF.setdefault('theme', False)
    APPCONF.setdefault('fmextensions', True)
    APPCONF.setdefault('daemons', '~/.config/yandex-disk/config.cfg')
    # Is it a first run?
    if not APPCONF.readSuccess:
        LOGGER.info('No config, probably it is a first run.')
        # Create application config folders in ~/.config
        try:
            makeDirs(APPCONFPATH)
            makeDirs(pathJoin(APPCONFPATH, 'icons/light'))
            makeDirs(pathJoin(APPCONFPATH, 'icons/dark'))
            # Copy icon themes readme to user config catalogue
            copyFile(pathJoin(APPINSTPATH, 'icons/readme'), pathJoin(APPCONFPATH, 'icons/readme'))
        except:
            sysExit(_('Can\'t create configuration files in %s') % APPCONFPATH)
        # Activate indicator automatic start on system start-up
        if not pathExists(APPAUTOSTARTDST):
            try:
                makeDirs(expanduser('~/.config/autostart'))
                copyFile(APPAUTOSTARTSRC, APPAUTOSTARTDST)
                APPCONF['autostart'] = True
            except:
                LOGGER.error('Can\'t activate indicator automatic start on system start-up')

        # Activate FM actions according to config (as it is first run)
        activateActions(APPCONF['fmextensions'], APPINSTPATH)
        # Default settings should be saved (later)
        APPCONF.changed = True

    # Add new daemon if it is not in current list
    daemons = [expanduser(d) for d in CVal(APPCONF['daemons'])]
    if args.cfg:
        args.cfg = expanduser(args.cfg)
        if args.cfg not in daemons:
            daemons.append(args.cfg)
            APPCONF.changed = True
    # Remove daemon if it is in the current list
    if args.rcfg:
        args.rcfg = expanduser(args.rcfg)
        if args.rcfg in daemons:
            daemons.remove(args.rcfg)
            APPCONF.changed = True
    # Check that at least one daemon is in the daemons list
    if not daemons:
        sysExit(_('No daemons specified.\nCheck correctness of -r and -c options.'))
    # Update config if daemons list has been changed
    if APPCONF.changed:
        APPCONF['daemons'] = CVal(daemons).get()
        # Update configuration file
        APPCONF.save()

    # Make indicator objects for each daemon in daemons list
    APPINDICATORS = []
    for dm in daemons:
        APPINDICATORS.append(Indicator(dm, _('#%d ') % len(APPINDICATORS) if len(daemons) > 1 else ''))

    # Register the SIGINT/SIGTERM handler for graceful exit when indicator is killed
    unix_signal_add(PRIORITY_HIGH, SIGINT, appExit)
    unix_signal_add(PRIORITY_HIGH, SIGTERM, appExit)
    # Start GTK Main loop
    Gtk.main()
