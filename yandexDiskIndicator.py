#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Yandex.Disk indicator (see appVersion variable in main loop code below for version info)
#
#  Copyright 2014 Sly_tom_cat <slytomcat@mail.ru>
#  based on grive-tools (C) Christiaan Diedericks (www.thefanclub.co.za)
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import AppIndicator3 as appindicator
from gi.repository import GdkPixbuf
from gi.repository import Notify
from shutil import copy as fileCopy
from tempfile import NamedTemporaryFile as newTempFile
from webbrowser import open_new as openNewBrowser
import os, sys, subprocess, pyinotify, fcntl, gettext, datetime

def debugPrint(textToPrint):
  global verboseDebug
  if verboseDebug:
    try:    print('%s: %s' % (datetime.datetime.now().strftime("%M:%S.%f"), textToPrint))
    except: pass

def sendmessage(title, message):
  global notificationSetting, notifier
  if notificationSetting:
    debugPrint('Message :%s' % message)
    notifier.update(title, message, yandexDiskIcon)    # Update notification
    notifier.show()                                    # Display new notification

def copyFile(source, destination):
  try:    fileCopy (source, destination)
  except: debugPrint("File Copy Error: from %s to %s" % (source, destination))

def deleteFile(source):
  try:    os.remove(source)
  except: debugPrint('File Deletion Error: %s' % source)

def stopTimer(timerName):
  if timerName > 0:
    GLib.source_remove(timerName)

def appExit():
  lockFile.write('')
  fcntl.flock(lockFile, fcntl.LOCK_UN)
  lockFile.close()
  os._exit(0)

def quitApplication(widget):
  global iconAnimationTimer, iNotifierTimer, watchTimer, currentStatus
  try:    stopOnExit = settings.get_boolean("stoponexit")
  except: stopOnExit = False
  debugPrint('Stop daemon on exit is - %s' % str(stopOnExit))
  if stopOnExit and currentStatus != 'none':
    stopYDdaemon()    # Stop daemon
    debugPrint('Daemon is stopped')
  # --- Stop all timers ---
  stopTimer(iconAnimationTimer)
  stopTimer(iNotifierTimer)
  stopTimer(watchTimer)
  debugPrint("Timers are closed")
  appExit()

def openLast(widget, index):  # Open last synchronized item
  global pathsList
  openPath(widget, pathsList[index])

def openPath(widget, path):  # Open path
  debugPrint('Opening %s' % path)
  if os.path.exists(path):
    try:    os.startfile(path)
    except: subprocess.call(['xdg-open', path])

def openInBrowser(widget, url):
  openNewBrowser(url)

def iNotifyHandler():  # iNotify working routine (called by timer)
  global iNotifier
  while iNotifier.check_events():
    iNotifier.read_events()
    iNotifier.process_events()
  return True

def daemonErrorDialog(err):   # Show error messages according to the error
  if err == 'NOCONFIG':
    dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK_CANCEL, 
                               _('Yandex.Disk Indicator: daemon start failed'))
    dialog.format_secondary_text(_('Yandex.Disk daemon failed to start because it is not' +
      ' configured properly\n  To configure it up: press OK button.\n  Press Cancel to exit.'))
  else:
    dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
                               _('Yandex.Disk Indicator: daemon start failed'))
    if err == 'NONET':
      dialog.format_secondary_text(_('Yandex.Disk daemon failed to start due to network' +
        ' connection issue. \n  Check the Internet connection and try to start daemon again.'))
    elif err == 'NOTINSTALLED':
      dialog.format_secondary_text(_('Yandex.Disk utility is not installed.\n ' +
        'Visit www.yandex.ru, download and install Yandex.Disk daemon.'))
    else:
      dialog.format_secondary_text(_('Yandex.Disk daemon failed to start due to some ' +
                                     'unrecognised error.'))
  dialog.set_default_size(400, 250)
  dialog.set_icon(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  response = dialog.run()
  dialog.destroy()
  if (err == 'NOCONFIG') and (response == Gtk.ResponseType.OK):  # Launch Set-up utility
    debugPrint('starting configuration utility: %s' % os.path.join(installDir, 'ya-setup'))
    retCode = subprocess.call([os.path.join(installDir,'ya-setup')])
  else:
    retCode = 0 if err == 'NONET' else 1
  return retCode              # 0 when error is not critical or fixed (daemon has been configured)

def openAbout(widget):          # Show About window
  widget.set_sensitive(False)   # Disable menu item
  aboutWindow = Gtk.AboutDialog(_('Yandex.Disk indicator'))
  logo = GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon)
  aboutWindow.set_logo(logo)
  aboutWindow.set_icon(logo)
  aboutWindow.set_program_name(_('Yandex.Disk indicator'))
  aboutWindow.set_version(_('Version ') + appVersion)
  aboutWindow.set_copyright('Copyright ' + u'\u00a9' + ' 2013-' + 
                            datetime.datetime.now().strftime("%Y") + '\nSly_tom_cat')
  aboutWindow.set_comments(_('Yandex.Disk indicator \n(Grive Tools was used as example)'))
  aboutWindow.set_license(
    'This program is free software: you can redistribute it and/or \n' +
    'modify it under the terms of the GNU General Public License as \n' +
    'published by the Free Software Foundation, either version 3 of \n' +
    'the License, or (at your option) any later version.\n\n' +
    'This program is distributed in the hope that it will be useful, \n' +
    'but WITHOUT ANY WARRANTY; without even the implied warranty \n' +
    'of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. \n' +
    'See the GNU General Public License for more details.\n\n' +
    'You should have received a copy of the GNU General Public License \n' +
    'along with this program.  If not, see http://www.gnu.org/licenses')
  aboutWindow.set_authors([_('Sly_tom_cat (slytomcat@mail.ru) '),
    _('ya-setup utility author: Snow Dimon (snowdimon.ru)'),
    _('\nSpecial thanks to:'),
    _(' - Christiaan Diedericks (www.thefanclub.co.za) - Grive tools creator'),
    _(' - ryukusu_luminarius (my-faios@ya.ru) - icons designer'),
    _(' - metallcorn (metallcorn@jabber.ru) - icons designer'),
    _(' - Chibiko (zenogears@jabber.ru) - deb package creation assistance'),
    _(' - RingOV (ringov@mail.ru) - localization assistance'),
    _(' - GreekLUG team (https://launchpad.net/~greeklug) - Greek translation'),
    _(' - And to all other people who contributed to this project through'),
    _('   the Ubuntu.ru forum http://forum.ubuntu.ru/index.php?topic=241992)')])
  aboutWindow.run()
  aboutWindow.destroy()
  widget.set_sensitive(True)    # Enable menu item

def onCheckButtonToggled(widget, button, key):  # Handle clicks on check-buttons
  global notificationSetting, settings, overwrite_check_button
  toggleState = button.get_active()
  settings.set_boolean(key, toggleState)        # Update dconf settings
  debugPrint('Togged: %s  val: %s' % (key, str(toggleState)))
  if key == 'theme':
    updateIconTheme()                           # Update themeStyle
    updateIcon()                                # Update current icon
  elif key == 'notifications':
    notificationSetting = toggleState           # Update notifications variable
  elif key == 'autostartdaemon':
    if toggleState:
      copyFile(autoStartSource1, autoStartDestination1)
      sendmessage(_('Yandex.Disk daemon'), _('Auto-start ON'))
    else:
      deleteFile(autoStartDestination1)
      sendmessage(_('Yandex.Disk daemon'), _('Auto-start OFF'))
  elif key == 'autostart':
    if toggleState:
      copyFile(autoStartSource, autoStartDestination)
      sendmessage(_('Yandex.Disk Indicator'), _('Auto-start ON'))
    else:
      deleteFile(autoStartDestination)
      sendmessage(_('Yandex.Disk Indicator'), _('Auto-start OFF'))
  elif key == 'fmextensions':
    activateActions()
  elif key == 'optionreadonly':
    overwrite_check_button.set_sensitive(toggleState)

def openPreferences(menu_widget):   # Preferences Window
  global settings, overwrite_check_button
  menu_widget.set_sensitive(False)  # Disable menu item to avoid multiple preferences windows
  # Create Preferences window
  preferencesWindow = Gtk.Dialog(_('Yandex.Disk-indicator and Yandex.Disk preferences'))
  preferencesWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  preferencesWindow.set_border_width(6)
  preferencesWindow.add_button(_('Close'), Gtk.ResponseType.CLOSE)
  pref_notebook = Gtk.Notebook()    # Create notebook for indicator and daemon options
  preferencesWindow.get_content_area().add(pref_notebook)  # Put it inside the dialog content area
  # --- Indicator preferences tab ---
  preferencesBox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
  key = 'autostart'                 # Auto-start indicator on system start-up
  autostart_check_button = Gtk.CheckButton(
                             _('Start Yandex.Disk indicator when you start your computer'))
  autostart_check_button.set_active(settings.get_boolean(key))
  autostart_check_button.connect("toggled", onCheckButtonToggled, autostart_check_button, key)
  settings.bind(key, autostart_check_button, 'active', Gio.SettingsBindFlags.GET)
  preferencesBox.add(autostart_check_button)
  key = 'startonstart'              # Start daemon on indicator start
  start_check_button = Gtk.CheckButton(_('Start Yandex.Disk daemon when indicator is starting'))
  start_check_button.set_tooltip_text(_("When daemon was not started before."))
  start_check_button.set_active(settings.get_boolean(key))
  start_check_button.connect("toggled", onCheckButtonToggled, start_check_button, key)
  settings.bind(key, start_check_button, 'active', Gio.SettingsBindFlags.GET)
  preferencesBox.add(start_check_button)
  key = 'stoponexit'                # Stop daemon on exit
  stop_check_button = Gtk.CheckButton(_('Stop Yandex.Disk daemon on closing of indicator'))
  stop_check_button.set_active(settings.get_boolean(key))
  stop_check_button.connect("toggled", onCheckButtonToggled, stop_check_button, key)
  settings.bind(key, stop_check_button, 'active', Gio.SettingsBindFlags.GET)
  preferencesBox.add(stop_check_button)
  key = 'notifications'             # Notifications
  notifications_check_button = Gtk.CheckButton(_('Show on-screen notifications'))
  notifications_check_button.set_active(settings.get_boolean(key))
  notifications_check_button.connect("toggled", onCheckButtonToggled,
                                     notifications_check_button, key)
  settings.bind(key, notifications_check_button, 'active', Gio.SettingsBindFlags.GET)
  preferencesBox.add(notifications_check_button)
  key = 'theme'                     # Theme
  theme_check_button = Gtk.CheckButton(_('Prefer light icon theme'))
  theme_check_button.set_active(settings.get_boolean(key))
  theme_check_button.connect("toggled", onCheckButtonToggled, theme_check_button, key)
  settings.bind(key, theme_check_button, 'active', Gio.SettingsBindFlags.GET)
  preferencesBox.add(theme_check_button)
  key = 'fmextensions'              # Activate file-manager extensions
  fmext_check_button = Gtk.CheckButton(_('Activate file manager extensions'))
  fmext_check_button.set_active(settings.get_boolean(key))
  fmext_check_button.connect("toggled", onCheckButtonToggled, fmext_check_button, key)
  settings.bind(key, fmext_check_button, 'active', Gio.SettingsBindFlags.GET)
  preferencesBox.add(fmext_check_button)
  # --- End of Indicator preferences tab --- add it to notebook
  pref_notebook.append_page(preferencesBox, Gtk.Label(_('Indicator settings')))
  # --- Daemon start options tab ---
  optionsBox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
  key = 'autostartdaemon'           # Auto-start daemon on system start-up
  autostart_d_check_button = Gtk.CheckButton(
                               _('Start Yandex.Disk daemon when you start your computer'))
  autostart_d_check_button.set_active(settings.get_boolean(key))
  autostart_d_check_button.connect("toggled", onCheckButtonToggled, autostart_d_check_button, key)
  settings.bind(key, autostart_d_check_button, 'active', Gio.SettingsBindFlags.GET)
  optionsBox.add(autostart_d_check_button)
  key = 'optionreadonly'            # Option Read-Only
  readOnly_check_button = Gtk.CheckButton(
                            _('Read-Only: Do not upload locally changed files to Yandex.Disk'))
  readOnly_check_button.set_tooltip_text(
    _("Locally changed files will be renamed if a newer version of this file appear in " + 
      "Yandex.Disk. \n NOTE! You have to reload daemon to activate this setting"))
  readOnly_check_button.set_active(settings.get_boolean(key))
  readOnly_check_button.connect("toggled", onCheckButtonToggled, readOnly_check_button, key)
  settings.bind(key, readOnly_check_button, 'active', Gio.SettingsBindFlags.GET)
  optionsBox.add(readOnly_check_button)
  key = 'optionoverwrite'           # Option Overwrite
  overwrite_check_button = Gtk.CheckButton(_('Overwrite locally changed files by files' + 
                                             ' from Yandex.Disk (in read-only mode)'))
  overwrite_check_button.set_tooltip_text(
    _("Locally changed files will be overwritten if a newer version of this file appear " + 
      "in Yandex.Disk. \n NOTE! You have to reload daemon to activate this setting"))
  overwrite_check_button.set_active(settings.get_boolean(key))
  overwrite_check_button.set_sensitive(settings.get_boolean('optionreadonly'))
  overwrite_check_button.connect("toggled", onCheckButtonToggled, overwrite_check_button, key)
  settings.bind(key, overwrite_check_button, 'active', Gio.SettingsBindFlags.GET)
  optionsBox.add(overwrite_check_button)
  # --- End of Daemon start options tab --- add it to notebook
  pref_notebook.append_page(optionsBox, Gtk.Label(_('Daemon options')))
  preferencesWindow.show_all()
  preferencesWindow.run()
  preferencesWindow.destroy()
  optionsSave()                     # Save daemon statrt options in config file
  menu_widget.set_sensitive(True)   # Enable menu item

def showOutput(menu_widget):                    # Display daemon output in dialogue window
  global origLANG, workLANG, daemonOutput
  menu_widget.set_sensitive(False)              # Disable menu item
  os.putenv('LANG', origLANG)                   # Restore user LANG settings
  getDaemonOutput()                             # Receve daemon output in user language
  os.putenv('LANG', workLANG)                   # Restore working LANG settings
  statusWindow = Gtk.Dialog(_('Yandex.Disk daemon output message'))
  statusWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  statusWindow.set_border_width(6)
  statusWindow.add_button(_('Close'), Gtk.ResponseType.CLOSE)
  textBox = Gtk.TextView()                      # Create text-box to display daemon output 
  textBox.get_buffer().set_text(daemonOutput)
  textBox.set_editable(False)
  statusWindow.get_content_area().add(textBox)  # Put it inside the dialogue content area
  statusWindow.show_all()
  statusWindow.run()
  statusWindow.destroy()
  menu_widget.set_sensitive(True)               # Enable menu item

def renderMenu():                           # Render initial menu (without any actual information)
  global menu_status, menu_used, menu_free, menu_YD_daemon_stop, menu_YD_daemon_start
  global menu_last, submenu_last, pathsList, yandexDiskFolder
  menu = Gtk.Menu()                         # Create menu
  menu_status = Gtk.MenuItem();   menu_status.connect("activate", showOutput)
  menu.append(menu_status)
  menu_used = Gtk.MenuItem();     menu_used.set_sensitive(False)
  menu.append(menu_used)
  menu_free = Gtk.MenuItem();     menu_free.set_sensitive(False)
  menu.append(menu_free)
  menu_last = Gtk.MenuItem(_('Last synchronized items'))
  submenu_last = Gtk.Menu()                 # Sub-menu: list of last synchronized files/folders
  pathsList = []                            # List of files/folders in lastMenu items
  menu_last.set_submenu(submenu_last)       # Add submenu (empty at the start)
  menu.append(menu_last)
  menu.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
  menu_YD_daemon_start = Gtk.MenuItem(_('Start Yandex.Disk daemon'))
  menu_YD_daemon_start.connect("activate", startDaemon); menu.append(menu_YD_daemon_start)
  menu_YD_daemon_stop = Gtk.MenuItem(_('Stop Yandex.Disk daemon'))
  menu_YD_daemon_stop.connect("activate", stopDaemon);   menu.append(menu_YD_daemon_stop)
  menu_open_YD_folder = Gtk.MenuItem(_('Open Yandex.Disk Folder'))
  menu_open_YD_folder.connect("activate", openPath, yandexDiskFolder)
  menu.append(menu_open_YD_folder)
  menu_open_YD_web = Gtk.MenuItem(_('Open Yandex.Disk on the web'))
  menu_open_YD_web.connect("activate", openInBrowser, 'http://disk.yandex.ru')
  menu.append(menu_open_YD_web)
  menu.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
  menu_preferences = Gtk.MenuItem(_('Preferences'))
  menu_preferences.connect("activate", openPreferences); menu.append(menu_preferences)
  menu_help = Gtk.MenuItem(_('Help'))
  menu_help.connect("activate", openInBrowser, 'https://yandex.ru/support/disk/')
  menu.append(menu_help)
  menu_about = Gtk.MenuItem(_('About'))
  menu_about.connect("activate", openAbout)
  menu.append(menu_about)
  menu.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
  menu_quit = Gtk.MenuItem(_('Quit'))
  menu_quit.connect("activate", quitApplication); menu.append(menu_quit)
  menu.show_all()
  return menu

def startYDdaemon():      # Execute 'yandex-disk start' 
                          # and return '' if success or error message if not
                          # ... but sometime it starts successfully with error message
  try:
    msg = subprocess.check_output(['yandex-disk', 'start'], universal_newlines=True)
    debugPrint('Start success, message: %s' % msg)
    return ''
  except subprocess.CalledProcessError as e:
    debugPrint('Start failed:%s' % e.output)
    if e.output == '':    # probably 'os: no file'
      return 'NOTINSTALLED'
    err = ('NONET' if 'Proxy' in e.output else 
           'BADDAEMON' if 'daemon' in e.output else 
           'NOCONFIG')
    return err

def startDaemon(widget):  # Try to start yandex-disk daemon and change the menu items sensitivity
  err = startYDdaemon()
  if err == '':
    updateStartStop(True)
  else:
    daemonErrorDialog(err)
    updateStartStop(False)

def stopYDdaemon():  # Execute 'yandex-disk stop'
  try:    msg = subprocess.check_output(['yandex-disk', 'stop'], universal_newlines=True)
  except: msg = ''
  return (msg != '')

def stopDaemon(widget):
  stopYDdaemon()
  updateStartStop(False)

def getDaemonOutput():
  global daemonOutput
  try:    daemonOutput = subprocess.check_output(['yandex-disk', 'status'], universal_newlines=True)
  except: daemonOutput = ''     # daemon is not running or bad
  if not PY3:                   # Decode required for python 2.7 and not required for Python3
    daemonOutput = daemonOutput.decode('utf-8')
  #debugPrint('output = %s' % daemonOutput)
  return (daemonOutput != '')

def parseDaemonOutput():                   # Parse the daemon output
  # Pre-formats status messages for menu
  global currentStatus, lastStatus, yandexDiskStatus, yandexDiskSpace1, yandexDiskSpace2
  global syncProgress, lastItems, lastItemsChanged, daemonOutput, YD_STATUS
  # Look for synchronization progress
  lastPos = 0
  startPos = daemonOutput.find('ync progress: ')
  if startPos > 0:
    startPos += 14                         # 14 is a length of 'ync progress: ' string
    lastPos = daemonOutput.find('\n', startPos)
    syncProgress = daemonOutput[startPos: lastPos]
  else:
    syncProgress = ''
  if daemonOutput != '':
    # Look for current core status (it is always presented in output); 13 is len('core status: ')
    startPos = daemonOutput.find('core status: ', lastPos) + 13  
    lastPos = daemonOutput.find('\n', startPos)
    currentStatus = daemonOutput[startPos: lastPos]
    if currentStatus == 'index':          # Don't handle index status
      currentStatus = lastStatus          # keep last status
  else:
    currentStatus = 'none'
  # Look for total Yandex.Disk size
  startPos = daemonOutput.find('Total: ', lastPos)
  if startPos > 0:
    startPos += 7                         # 7 is len('Total: ')
    lastPos = daemonOutput.find('\n', startPos)
    sTotal = daemonOutput[startPos: lastPos]
    ## If 'Total: ' was found then other information as also should be presented
    # Look for used size                  # 6 is len('Used: ')
    startPos = daemonOutput.find('Used: ', lastPos) + 6
    lastPos = daemonOutput.find('\n', startPos)
    sUsed = daemonOutput[startPos: lastPos]
    # Look for free size                  # 11 is len('Available: ')
    startPos = daemonOutput.find('Available: ', lastPos) + 11
    lastPos = daemonOutput.find('\n', startPos)
    sFree = daemonOutput[startPos: lastPos]
    # Look for trash size                 # 12 is len('Trash size: ')
    startPos = daemonOutput.find('Trash size: ', lastPos) + 12
    lastPos = daemonOutput.find('\n', startPos)
    sTrash = daemonOutput[startPos: lastPos]
  else:  # When there is no Total: then other sizes are not presented
    sTotal = '...'
    sUsed = '...'
    sFree = '...'
    sTrash = '...'
  # Look for last synchronized items list
  startPos = daemonOutput.find('Last synchronized', lastPos)
  if startPos > 0:                        # skip one line
    startPos = daemonOutput.find('\n', startPos) + 1
    buf = daemonOutput[startPos: ]        # save the rest
  else:
    buf = ''
  lastItemsChanged = (lastItems != buf)   # check changes in the list 
  #debugPrint(str(lastItemsChanged))
  lastItems = buf
  # Don't split last synchronized list on individual lines/paths
  # It is easier to do it in the same loop where menu is being updated (in updateMenuInfo()).  
  # Prepare and format information for menu
  yandexDiskStatus = _('Status: ') + YD_STATUS.get(currentStatus, _('Error')) + syncProgress
  yandexDiskSpace1 = _('Used: ') + sUsed + '/' + sTotal
  yandexDiskSpace2 = _('Free: ') + sFree + _(', trash: ') + sTrash

def checkDaemon():               # Checks that daemon installed, configured and it is running.
  # it also reads the configuration file in any case when it returns
  global settings
  if not os.path.exists('/usr/bin/yandex-disk'):
    daemonErrorDialog('NOTINSTALLED')
    appExit()                    # Daemon is not installed. Exit right now.
  while not readConfig():        # Try to read Yandex.Disk configuration file
    if daemonErrorDialog('NOCONFIG') != 0:
      appExit()                  # User hasn't configured daemon. Exit right now.
  while not getDaemonOutput():   # Check for correct daemon response (also check that it is running)
    try:                         # Try to find daemon running process
      msg = subprocess.check_output(['pgrep', '-x', 'yandex-disk'], universal_newlines=True)[: -1]
      debugPrint('yandex-disk daemon is running but NOT responding!')
      # Kills the daemon(s) when it is running but not responding (HARON_CASE).
      try:                       # Try to kill all instances of daemon
        subprocess.check_call(['killall', 'yandex-disk'])
        debugPrint('yandex-disk daemon(s) killed')
        msg = ''
      except:
        debugPrint('yandex-disk daemon kill error')
        daemonErrorDialog('')
        appExit()                # nonconvertible error - exit 
    except:
      debugPrint("yandex-disk daemon is not running")
      msg = ''
    if msg == '' and not settings.get_boolean("startonstart"):  
      return False               # Daemon is not started and should not be started
    else:  
      err = startYDdaemon()      # Try to start it
      if err != '':
        if daemonErrorDialog(err) != 0:
          appExit()              # Something wrong. It's no way to continue. Exit right now.
        else:
          return False           # Daemon was not started but user decided to start indicator anyway
    # here we started daemon. Try to check it's output (in while)
  # At this point we know that daemon is installed, configured and started
  debugPrint('yandex-disk daemon is responding correctly.')
  return True                    # Everything OK

def updateMenuInfo():                           # Update information in menu
  global menu_last, submenu_last, pathsList, lastItems, lastItemsChanged, yandexDiskStatus
  global yandexDiskSpace1, yandexDiskSpace2, menu_status, menu_used, menu_free
  menu_status.set_label(yandexDiskStatus)       # Update status data
  menu_used.set_label(yandexDiskSpace1)
  menu_free.set_label(yandexDiskSpace2)
  # --- Update last synchronized list ---
  if lastItemsChanged:                          # only when list of last synchronized is changed
    for widget in submenu_last.get_children():  # clear last synchronized sub menu 
      submenu_last.remove(widget)
    pathsList = []                              # clear list of file paths 
    for listLine in lastItems.splitlines():
      startPos = listLine.find(": '")           # Find file path in the line
      if (startPos > 0):                        # File path was found
        filePath = listLine[startPos + 3: - 1]  # Get relative file path (skip quotes)
        pathsList.append(os.path.join(yandexDiskFolder, filePath))    # Store fill file path
        # Make menu label as file path (shorten to 50 symbols if path length > 50 symbols), 
        # with replaced underscore (to disable menu acceleration feature of GTK menu).
        widget = Gtk.MenuItem.new_with_label(
                   (filePath[: 20] + '...' + filePath[-27: ] if len(filePath) > 50 else
                    filePath).replace('_', u"\u02CD"))
        if os.path.exists(pathsList[-1]):
          widget.set_sensitive(True)            # It can be opened
          widget.connect("activate", openLast, len(pathsList) - 1)
        else:
          widget.set_sensitive(False)
        submenu_last.append(widget)
        widget.show()
    if len(pathsList) == 0:                     # no items in list
      menu_last.set_sensitive(False)
    else:                                       # there are some items in list
      menu_last.set_sensitive(True)
  
def updateStartStop(started):   # Update daemon start and stop menu items availability
  global menu_YD_daemon_start, menu_YD_daemon_stop, menu_status
  if started:
    menu_YD_daemon_start.set_sensitive(False)
    menu_YD_daemon_stop.set_sensitive(True)
    menu_status.set_sensitive(True)
  else:
    menu_YD_daemon_start.set_sensitive(True)
    menu_YD_daemon_stop.set_sensitive(False)
    menu_status.set_sensitive(False)

def handleEvent(triggeredBy_iNotifier): # Main working routine: event handler function.
  # It react (icon change/messages) on status change and also update
  # status information in menu (status, sizes, last synchronized items).
  # It can be called asynchronously by timer (triggeredBy_iNotifier=False)
  # or by iNonifier (triggeredBy_iNotifier=True)
  global currentStatus, newStatus, lastStatus, watchTimer, timerTriggeredCount
  getDaemonOutput()                 # Get the latest status data from daemon
  parseDaemonOutput()               # Parse it
  # Convert status to the internal presentation ['busy','idle','paused','none','error']
  newStatus = currentStatus if currentStatus in ['busy', 'idle', 'paused', 'none'] else 'error'
  # Status 'error' covers 'error', 'no internet access','failed to connect to daemon process'...
  debugPrint('Event triggered by %s  status: %s -> %s' % ('inotify' if triggeredBy_iNotifier else
                                                          'timer  ', lastStatus, newStatus))
  updateMenuInfo()                  # Update information in menu
  if lastStatus != newStatus:       # Handle status change
    updateIcon()                    # Update icon
    if lastStatus == 'none':        # Daemon was just started when 'none' changed to something else
      updateStartStop(True)         # Change menu sensitivity
      sendmessage(_('Yandex.Disk'), _('Yandex.Disk daemon is started'))
    if newStatus == 'busy':         # Just entered into 'busy'
      sendmessage(_('Yandex.Disk'), _('Synchronization is started'))
    elif newStatus == 'idle':       # Just entered into 'idle'
      if lastStatus == 'busy':      # ...from 'busy' status
        sendmessage(_('Yandex.Disk'), _('Synchronization is finished'))
    elif newStatus =='paused':      # Just entered into 'paused'
      if lastStatus != 'none':      # ...not from 'none' status
        sendmessage(_('Yandex.Disk'), _('Synchronization is paused'))
    elif newStatus == 'none':       # Just entered into 'none' from some another status
      updateStartStop(False)        # Change menu sensitivity as daemon not started
      sendmessage(_('Yandex.Disk'), _('Yandex.Disk daemon is stopped'))
    else:                           # newStatus = 'error' - Just entered into 'error'
      sendmessage(_('Yandex.Disk'), _('Synchronization ERROR'))
    lastStatus = newStatus          # remember new status
  # --- Handle timer delays ---
  if triggeredBy_iNotifier:         # True means that it is called by iNonifier
    stopTimer(watchTimer)           # Recreate timer with 2 sec interval.
    watchTimer = GLib.timeout_add_seconds(2, handleEvent, False)
    timerTriggeredCount = 0         # reset counter as it was triggered not by time watcher
  else:
    if newStatus != 'busy':         # in 'busy' keep last update interval (2 sec.)
      if timerTriggeredCount < 9:   # increase interval up to 10 sec (2+8)
        stopTimer(watchTimer)       # Recreate timer.
        watchTimer = GLib.timeout_add_seconds(2 + timerTriggeredCount, handleEvent, False)
        timerTriggeredCount += 1    # Increase cunt to increase delay in next time
  return True                       # To continue activations by timer.

def updateIconTheme():    # Update paths to icons according to current theme
  global iconThemePath, ind, icon_busy, icon_idle, icon_pause, icon_error
  
  try:                    # Read defaults from dconf Settings
    themeStyle = 'light' if settings.get_boolean("theme") else 'dark'
  except:
    themeStyle = 'dark'
  # --- Set appropriate paths to icons ---
  iconThemePath = os.path.join(installDir, 'icons', themeStyle )
  icon_busy =  os.path.join(iconThemePath, 'yd-busy1.png')
  icon_idle =  os.path.join(iconThemePath, 'yd-ind-idle.png')
  icon_pause = os.path.join(iconThemePath, 'yd-ind-pause.png')
  icon_error = os.path.join(iconThemePath, 'yd-ind-error.png')

def updateIcon():                     # Change indicator icon according to current status
  global newStatus, lastStatus, icon_busy, icon_idle, icon_pause
  global icon_error, iconAnimationTimer, seqNum, ind

  if newStatus == 'busy':             # Just entered into 'busy' status
    ind.set_icon(icon_busy)           # Start icon animation
    seqNum = 2                        # Start animation from next icon
    # Create animation timer
    iconAnimationTimer = GLib.timeout_add(777, iconAnimation, 'iconAnimation') 
  else:
    if newStatus != 'busy' and iconAnimationTimer > 0:  # Not 'busy' and animation is running
      stopTimer(iconAnimationTimer)   # Stop icon animation
      iconAnimationTimer = 0
    # --- Set icon for non-animated statuses ---
    if newStatus == 'idle':
      ind.set_icon(icon_idle)
    elif newStatus == 'error':
      ind.set_icon(icon_error)
    else:                             # newStatus is 'none' or 'paused'
      ind.set_icon(icon_pause)

def iconAnimation(widget):   # Changes busy icon by loop (triggered by iconAnimationTimer)
  global seqNum, ind, iconThemePath
  seqFile = 'yd-busy' + str(seqNum) + '.png'
  ind.set_icon(os.path.join(iconThemePath, seqFile))
  # calculate next icon number
  seqNum = seqNum % 5 + 1    # 5 icons in loop (1-2-3-4-5-1-2-3...)
  return True                # True required to continue triggering by timer

def activateActions():  # Install/deinstall file extensions
  try:                  # get settings
    activate = settings.get_boolean("fmextensions")
  except:
    activate = False
  # --- Actions for Nautilus ---
  ret = subprocess.call(["dpkg -s nautilus>/dev/null 2>&1"], shell=True)
  debugPrint("Nautilus installed: %s" % str(ret == 0))
  if ret == 0:
    ver = subprocess.check_output(["lsb_release -r | sed -n '1{s/[^0-9]//g;p;q}'"], shell=True)
    if ver != '' and int(ver) < 1210:
      nautilusPath = ".gnome2/nautilus-scripts/"
    else:
      nautilusPath = ".local/share/nautilus/scripts"
    debugPrint(nautilusPath)
    if activate:        # Install actions for Nautilus
      copyFile(os.path.join(installDir, "fm-actions/Nautilus_Nemo/publish"),
               os.path.join(userHome,nautilusPath, _("Publish via Yandex.Disk")))
      copyFile(os.path.join(installDir, "fm-actions/Nautilus_Nemo/unpublish"),
               os.path.join(userHome, nautilusPath, _("Unpublish from Yandex.disk")))
    else:               # Remove actions for Nautilus
      deleteFile(os.path.join(userHome, nautilusPath, _("Publish via Yandex.Disk")))
      deleteFile(os.path.join(userHome, nautilusPath, _("Unpublish from Yandex.disk")))
  # --- Actions for Nemo ---
  ret = subprocess.call(["dpkg -s nemo>/dev/null 2>&1"], shell=True)
  debugPrint("Nemo installed: %s" % str(ret == 0))
  if ret == 0:
    if activate:        # Install actions for Nemo
      copyFile(os.path.join(installDir, "fm-actions/Nautilus_Nemo/publish"),
               os.path.join(userHome, ".local/share/nemo/scripts",
                            _("Publish via Yandex.Disk")))
      copyFile(os.path.join(installDir, "fm-actions/Nautilus_Nemo/unpublish"),
               os.path.join(userHome, ".local/share/nemo/scripts",
                            _("Unpublish from Yandex.disk")))
    else:               # Remove actions for Nemo
      deleteFile(os.path.join(userHome, ".gnome2/nemo-scripts",
                              _("Publish via Yandex.Disk")))
      deleteFile(os.path.join(userHome, ".gnome2/nemo-scripts",
                              _("Unpublish from Yandex.disk")))
  # --- Actions for Thunar ---
  ret = subprocess.call(["dpkg -s thunar>/dev/null 2>&1"], shell=True)
  debugPrint("Thunar installed: %s" % str(ret == 0))
  if ret == 0:
    if activate:        # Install actions for Thunar
      if subprocess.call(["grep '" + _("Publish via Yandex.Disk") + "' " +
                          os.path.join(userHome, ".config/Thunar/uca.xml") + " >/dev/null 2>&1"],
                         shell=True) != 0:
        subprocess.call(["sed", "-i", "s/<\/actions>/<action><icon>folder-publicshare<\/icon>" +
                         '<name>"' + _("Publish via Yandex.Disk") +
                         '"<\/name><command>yandex-disk publish %f | xclip -filter -selection' +
                         ' clipboard; zenity --info ' +
                         '--window-icon=\/opt\/yd-tools\/icons\/yd-128.png --title="Yandex.Disk"' +
                         ' --ok-label="' + _('Close') + '" --text="' +
                         _('URL to file: %f has copied into clipboard.') +
                         '"<\/command><description><\/description><patterns>*<\/patterns>' +
                         '<directories\/><audio-files\/><image-files\/><other-files\/>' +
                         "<text-files\/><video-files\/><\/action><\/actions>/g",
                        os.path.join(userHome, ".config/Thunar/uca.xml")])
      if subprocess.call(["grep '" + _("Unpublish from Yandex.disk") + "' " +
                          os.path.join(userHome,".config/Thunar/uca.xml") + " >/dev/null 2>&1"],
                          shell=True) != 0:
        subprocess.call(["sed", "-i", "s/<\/actions>/<action><icon>folder<\/icon><name>\"" +
                         _("Unpublish from Yandex.disk") +
                         '"<\/name><command>zenity --info ' +
                         '--window-icon=\/opt\/yd-tools\/icons\/yd-128_g.png --ok-label="' +
                         _('Close') + '" --title="Yandex.Disk" --text="' +
                         _("Unpublish from Yandex.disk") +
                         ': \`yandex-disk unpublish %f\`"<\/command>' +
                         '<description><\/description><patterns>*<\/patterns>' +
                         '<directories\/><audio-files\/><image-files\/><other-files\/>' +
                         "<text-files\/><video-files\/><\/action><\/actions>/g",
                        os.path.join(userHome, ".config/Thunar/uca.xml")])
    else:               # Remove actions for Thunar
      subprocess.call(["sed", "-i", "s/<action><icon>.*<\/icon><name>\"" +
                       _("Publish via Yandex.Disk") + "\".*<\/action>//",
                      os.path.join(userHome,".config/Thunar/uca.xml")])
      subprocess.call(["sed", "-i", "s/<action><icon>.*<\/icon><name>\"" +
                       _("Unpublish from Yandex.disk") + "\".*<\/action>//",
                      os.path.join(userHome, ".config/Thunar/uca.xml")])
  # --- Actions for Dolphin ---
  ret = subprocess.call(["dpkg -s dolphin>/dev/null 2>&1"], shell=True)
  debugPrint("Dolphin installed: %s" % str(ret == 0))
  if ret == 0:
    if activate:        # Install actions for Dolphin
      copyFile(os.path.join(installDir, "fm-actions/Dolphin/publish.desktop"),
               os.path.join(userHome, ".kde/share/kde4/services/publish.desktop"))
      copyFile(os.path.join(installDir, "fm-actions/Dolphin/unpublish.desktop"),
               os.path.join(userHome, ".kde/share/kde4/services/unpublish.desktop"))
    else:               # Remove actions for Dolphin
      deleteFile(os.path.join(userHome, ".kde/share/kde4/services/publish.desktop"))
      deleteFile(os.path.join(userHome," .kde/share/kde4/services/unpublish.desktop"))

def optionsSave():  # Update daemon config file according to the configuration settings
  global daemonConfig, settings
  roExist = False
  ovExist = False
  roVal = settings.get_boolean('optionreadonly')
  ovVal = settings.get_boolean('optionoverwrite')
  try:
    cfgFile = open(daemonConfig, 'rt')
  except:
    debugPrint('CFG File open error')
  else:             # Open new temporary file in text mode for write ad keep it after close
    newFile = newTempFile(mode='wt', delete=False)
    for line in cfgFile:
      if line.startswith('read-only='):
        roExist = True
        if not roVal:
          continue
      elif line.startswith('overwrite='):
        ovExist = True
        if not (roVal and ovVal):
          continue
      newFile.write(line)
    if roVal and not roExist:
      newFile.write('read-only=""\n')
    if ovVal and roVal and not ovExist:
      newFile.write('overwrite=""\n')
    cfgFile.close()
    newFile.close()
    deleteFile(daemonConfig)
    copyFile(newFile.name, daemonConfig)

def readConfig():     # Update settings according to daemon config file and get yandex.disk folder path
  global daemonConfig, yandexDiskFolder, settings
  roVal = False
  ovVal = False
  yandexDiskFolder = ''
  if not os.path.exists(daemonConfig):
    return False
  try:
    cfgFile = open(daemonConfig, 'rt')
  except:
    debugPrint('CFG File open error')
  else:
    for line in cfgFile:
      if line.startswith('read-only='):
        roVal = True
      if line.startswith('overwrite='):
        ovVal = True
      pos = line.find('dir=')+4
      if pos > 3:
        if line[pos] == '"':
          pos+=1
          yandexDiskFolder = line[pos: line.find('"', pos)]
        else:
          yandexDiskFolder = line[pos: line.find('/n', pos)]
        if not PY3:   # Decode required for python 2.7 and not required for Python3
          yandexDiskFolder = yandexDiskFolder.decode('utf-8')
        debugPrint('Config: yandexDiskFolder = %s' % yandexDiskFolder)
    cfgFile.close()
    settings.set_boolean('optionreadonly', roVal)
    settings.set_boolean('optionoverwrite', ovVal)
    return (yandexDiskFolder != '')

###################### MAIN LOOP #########################
if __name__ == '__main__':
  ### Running environment detection
  PY3 = sys.version_info[0] == 3
  installDir = os.path.dirname(os.path.realpath(__file__))
  userHome = os.getenv("HOME")
  ### Application constants and settings ###
  appVersion = '1.3.1_Py' + ('3' if PY3 else '2')
  appName = 'yandex-disk-indicator'
  # Define .desktop files locations for auto-start facility
  autoStartSource = os.path.join(installDir, 'Yandex.Disk-indicator.desktop')
  autoStartDestination = os.path.join(userHome, '.config', 'autostart',
                                      'Yandex.Disk-indicator.desktop')
  autoStartSource1 = os.path.join(installDir, 'Yandex.Disk.desktop')
  autoStartDestination1 = os.path.join(userHome, '.config', 'autostart', 'Yandex.Disk.desktop')
  # Yandex.Disk configuration file path
  daemonConfig = os.path.join(userHome, '.config', 'yandex-disk', 'config.cfg')
  # Store and set LANG environment for daemon output (it must be 'en' for correct parsing)
  origLANG = os.getenv('LANG')
  workLANG = 'en_US.UTF-8'
  os.putenv('LANG', workLANG)
  ### Configuration settings ###
  try:
    settings = Gio.Settings.new("apps." + appName)
  except:
    sys.exit('dconf settings are not found!')
  # Read some settings to variables
  try:
    verboseDebug = settings.get_boolean("debug")
  except:
    verboseDebug = False
  try:
    notificationSetting = settings.get_boolean("notifications")
  except:
    notificationSetting = True
  # Update auto-start settings according to actual files existence in ~/.config/autostart
  try:  
    settings.set_boolean('autostart', os.path.isfile(autoStartDestination))
    settings.set_boolean('autostartdaemon', os.path.isfile(autoStartDestination1))
  except:
    pass
  ### Localization ###
  debugPrint("Current Locale : %s" % origLANG)
  try:                        # Try to load translation
    if PY3:                   # use gettext in python3
      _ = gettext.translation(appName, '/usr/share/locale', fallback=True).gettext
    else:                     # use ugettext in python2.7 for UTF-8 support
      _ = gettext.translation(appName, '/usr/share/locale', fallback=True).ugettext
  except:
    _ = str                   # use original English as fallback
  ### Activate FM actions according to settings if lock file not exists (probably it is a first run)
  lockFileName = '/tmp/' + appName + '.lock'
  if not os.path.isfile(lockFileName):
    activateActions()
  ### Check for already running instance of the indicator application ###
  try:
    lockFile = open(lockFileName, 'w')                      # Open lock file for write
    fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)    # Try to acquire exclusive lock
  except:                                                   # File is already locked
    sys.exit(_('Yandex.Disk Indicator instance already running\n' +
               '(file /tmp/%s.lock is locked by another process)') % appName)
  lockFile.write('%d\n' % os.getpid())
  lockFile.flush()
  ### Yandex.Disk daemon ###
  # Initialize global variables
  YD_STATUS = {'idle': _('Synchronized'), 'busy': _('Sync.: '), 'none': _('Not started'),
               'paused': _('Paused'), 'no internet access': _('Not connected')}
  lastItems = ''
  currentStatus = 'none'
  lastStatus = 'idle'         # fallback status for "index" status substitution at start time
  if checkDaemon():           # Check that daemon is installed, configured and started (responding)
    parseDaemonOutput()       # Parse daemon output to get real currentStatus
  # Read Yandex.Disk configuration file is read in checkDaemon()
  ### Set initial statuses
  newStatus = lastStatus = currentStatus
  lastItems = '*'             # Reset lastItems in order to update menu in handleEvent()
  ### On-screen notifications ###
  Notify.init(appName)        # Initialize notification engine
  notifier = Notify.Notification()
  ### Application Indicator ###
  ## Icons ##
  yandexDiskIcon = os.path.join(installDir, 'icons', 'yd-128.png')            # Big icon
  updateIconTheme()           # Define the rest icons paths
  iconAnimationTimer = 0      # Define the icon animation timer variable
  ## Indicator ##
  ind = appindicator.Indicator.new("yandex-disk", icon_pause,
                                   appindicator.IndicatorCategory.APPLICATION_STATUS)
  ind.set_status(appindicator.IndicatorStatus.ACTIVE)
  ind.set_menu(renderMenu())  # Prepare and attach menu to indicator
  updateIcon()                # Update indicator icon according to current status
  ### Timer triggered event staff ###
  watchTimer = 0              # Timer source variable
  ### Initial menu actualisation ###
  handleEvent(True)           # True value will update info and create the watch timer for 2 sec
  updateStartStop(newStatus != 'none')
  ### File updates watcher ###
  class EventHandler(pyinotify.ProcessEvent):   # Event handler class for iNotifier
    def process_IN_MODIFY(self, event):
      #debugPrint( "Modified: %s" %  os.path.join(event.path, event.name))
      handleEvent(True)       # True means that handler called by iNotifier
  watchManager = pyinotify.WatchManager()                                     # Create watch manager
  iNotifier = pyinotify.Notifier(watchManager, EventHandler(), timeout=0.5)   # Create PyiNotifier
  watchManager.add_watch(os.path.join(yandexDiskFolder, '.sync/cli.log'),
                         pyinotify.IN_MODIFY, rec = False)                    # Add watch
  iNotifierTimer = GLib.timeout_add(700, iNotifyHandler)  # Call iNotifier handler every .7 seconds
  Gtk.main()                  # Start GTK Main loop
