#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  Yandex.Disk indicator v.1.2.3
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
import os
import sys
import subprocess
import datetime
import shutil
import tempfile
import webbrowser
import pyinotify
import fcntl
import gettext
import locale

def debugPrint(textToPrint):
  global verboseDebug
  if verboseDebug:
    try:
      print('%s: %s'%(datetime.datetime.now().strftime("%M:%S.%f"), textToPrint))
    except:
      pass

def sendmessage(title, message):
  global notificationSetting
  global notifier
  if notificationSetting:
    debugPrint('Message :%s'%message)
    notifier.update(title, message, yandexDiskIcon)    # Update notification
    notifier.show()                                    # Display new notification

def copyFile(source, destination):
  try:
    shutil.copy (source, destination)
  except:
    debugPrint("File Copy Error: from %s to %s" %(source,destination))

def deleteFile(source):
  try:
    os.remove(source)
  except:
    debugPrint('File Deletion Error: %s' % source)

def stopTimer(timerName):
  if timerName > 0:
    GLib.source_remove(timerName)
  return

def appExit():
  lockFile.write('')
  fcntl.flock(lockFile, fcntl.LOCK_UN)
  lockFile.close()
  os._exit(0)

def quitApplication(widget):
  global iconAnimationTimer
  global iNotifierTimer
  global watchTimer
  global currentStatus
  try:
    stopOnExit = settings.get_boolean("stoponexit")
  except:
    stopOnExit = False
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

def openLast(widget, index): # Open last synchronized item
  global yandexDiskFolder
  global pathsList
  path = pathsList[index]     # Get path by index
  if path != '...':
    openPath(widget, os.path.join(yandexDiskFolder,path))

def openPath(widget, path): # Open path
  debugPrint('Opening %s'%path)
  if os.path.exists(path):
    try:
      os.startfile(path)
    except:
      subprocess.Popen(['xdg-open', path])

def openInBrowser(widget, url):
  webbrowser.open_new(url)

def iNotifyHandler(): # iNotify working routine (called by timer)
  global iNotifier
  while iNotifier.check_events():
    iNotifier.read_events()
    iNotifier.process_events()
  return True

def daemonErrorDialog(err): # Show error messages according to the error
  if err == 'NOCONFIG':
    dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK_CANCEL, _('Yandex.Disk Indicator: daemon start failed'))
    dialog.format_secondary_text(_('Yandex.Disk daemon failed to start because it is not configured properly\n  To configure it up: press OK button.\n  Press Cancel to exit.'))
  else:
    dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, _('Yandex.Disk Indicator: daemon start failed'))
    if err == 'NONET':
      dialog.format_secondary_text(_('Yandex.Disk daemon failed to start due to network connection issue. \n  Check the Internet connection and try to start daemon again.'))
    elif err == 'NOTINSTALLED':
      dialog.format_secondary_text(_('Yandex.Disk utility is not installed.\n Visit www.yandex.ru, download and install Yandex.Disk daemon.'))
    else:
      dialog.format_secondary_text(_('Yandex.Disk daemon failed to start due to some unrecognised error.'))
  dialog.set_default_size(400, 250)
  response = dialog.run()
  dialog.destroy()
  if (err == 'NOCONFIG') and (response == Gtk.ResponseType.OK): # Launch Set-up utility
    debugPrint('starting configuration utility: %s'% os.path.join(installDir,'ya-setup'))
    retCode = subprocess.call([os.path.join(installDir,'ya-setup')])
  elif err == 'NONET':
    retCode = 0
  else:
    retCode = 1
  return retCode    # 0 when error is not critical or fixed (daemon has been configured)

def openAbout(widget):                    # Show About window
  widget.set_sensitive(False)             # Disable menu item
  aboutWindow = Gtk.AboutDialog()
  aboutWindow.set_name(_('Yandex.Disk indicator'))
  aboutWindow.set_version(_('Version ')+appVersion)
  aboutWindow.set_copyright('Copyright '+u'\u00a9'+
  ' 2013-'+datetime.datetime.now().strftime("%Y")+'\nSly_tom_cat')
  aboutWindow.set_comments(_('Yandex.Disk indicator \n(Grive Tools was used as example)'))
  aboutWindow.set_license(''+
  'This program is free software: you can redistribute it and/or \n'+
  'modify it under the terms of the GNU General Public License as \n'+
  'published by the Free Software Foundation, either version 3 of \n'+
  'the License, or (at your option) any later version.\n\n'+
  'This program is distributed in the hope that it will be useful, \n'+
  'but WITHOUT ANY WARRANTY; without even the implied warranty \n'+
  'of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. \n'+
  'See the GNU General Public License for more details.\n\n'+
  'You should have received a copy of the GNU General Public License \n'+
  'along with this program.  If not, see http://www.gnu.org/licenses')
  aboutWindow.set_authors([_('Sly_tom_cat (slytomcat@mail.ru) '),
  _('ya-setup utility author: Snow Dimon (snowdimon.ru)' ),
  _('\nSpecial thanks to:'),
  _(' - Christiaan Diedericks (www.thefanclub.co.za) - Grive tools creator'),
  _(' - ryukusu_luminarius (my-faios@ya.ru) - icons designer'),
  _(' - metallcorn (metallcorn@jabber.ru) - icons designer'),
  _(' - Chibiko (zenogears@jabber.ru) - deb package creation assistance'),
  _(' - RingOV (ringov@mail.ru) - localization assistance'),
  _(' - GreekLUG team (https://launchpad.net/~greeklug) - Greek translation'),
  _(' - And to all other people who contributed to this project through'),
  _('   the Ubuntu.ru forum http://forum.ubuntu.ru/index.php?topic=241992)')] )
  aboutWindow.set_logo(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  aboutWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  aboutWindow.set_program_name(_('Yandex.Disk indicator'))
  aboutWindow.run()
  aboutWindow.destroy()
  widget.set_sensitive(True)              # Enable back menu item

def onCheckButtonToggled(widget, button, key): # Handle clicks on check-buttons
  global notificationSetting
  global settings
  global overwrite_check_button
  toggleState = button.get_active()
  settings.set_boolean(key, toggleState)  # Update dconf settings
  debugPrint('Togged: '+key+'  val: '+str(toggleState))
  if key == 'theme':
    updateIconTheme()                     # Update themeStyle
    updateIcon()                          # Update current icon
  elif key == 'notifications':
    notificationSetting = toggleState     # Update notifications variable
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

def openPreferences(menu_widget): # Preferences Window
  global settings
  global overwrite_check_button
  menu_widget.set_sensitive(False)  # Disable menu item to avoid multiple preferences windows creation
  preferencesWindow = Gtk.Dialog()  # Create Preferences window
  preferencesWindow.set_title(_('Yandex.Disk-indicator and Yandex.Disk preferences'))
  preferencesWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  preferencesWindow.set_border_width(6)
  preferencesWindow.add_button(_('Close'),Gtk.ResponseType.CLOSE)
  pref_notebook = Gtk.Notebook()    # Create notebook for indicator and daemon options
  preferencesWindow.get_content_area().add(pref_notebook)  # Put it inside the dialog content area
  # --- Indicator preferences tab ---
  preferencesBox = Gtk.Box.new(Gtk.Orientation.VERTICAL,5)
  key = 'autostart'                 # Auto-start indicator on system start-up
  autostart_check_button = Gtk.CheckButton(_('Start Yandex.Disk indicator when you start your computer'))
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
  notifications_check_button.connect("toggled", onCheckButtonToggled, notifications_check_button, key)
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
  # --- End tab --- add it to notebook
  pref_notebook.append_page(preferencesBox, Gtk.Label(_('Indicator settings')))
  # --- Daemon start options tab ---
  optionsBox = Gtk.Box.new(Gtk.Orientation.VERTICAL,5)
  key = 'autostartdaemon'           # Auto-start daemon on system start-up
  autostart_d_check_button = Gtk.CheckButton(_('Start Yandex.Disk daemon when you start your computer'))
  autostart_d_check_button.set_active(settings.get_boolean(key))
  autostart_d_check_button.connect("toggled", onCheckButtonToggled, autostart_d_check_button, key)
  settings.bind(key, autostart_d_check_button, 'active', Gio.SettingsBindFlags.GET)
  optionsBox.add(autostart_d_check_button)
  key = 'optionreadonly'            # Option Read-Only
  readOnly_check_button = Gtk.CheckButton(_('Read-Only: Do not upload locally changed files to Yandex.Disk'))
  readOnly_check_button.set_tooltip_text(_("Locally changed files will be renamed if a newer version of this file appear in Yandex.Disk. \n NOTE! You have to reload daemon to activate this setting"))
  readOnly_check_button.set_active(settings.get_boolean(key))
  readOnly_check_button.connect("toggled", onCheckButtonToggled, readOnly_check_button, key)
  settings.bind(key, readOnly_check_button, 'active', Gio.SettingsBindFlags.GET)
  optionsBox.add(readOnly_check_button)
  key = 'optionoverwrite'           # Option Overwrite
  overwrite_check_button = Gtk.CheckButton(_('Overwrite locally changed files by files from Yandex.Disk (in read-only mode)'))
  overwrite_check_button.set_tooltip_text(_("Locally changed files will be overwritten if a newer version of this file appear in Yandex.Disk. \n NOTE! You have to reload daemon to activate this setting"))
  overwrite_check_button.set_active(settings.get_boolean(key))
  overwrite_check_button.set_sensitive(settings.get_boolean('optionreadonly'))
  overwrite_check_button.connect("toggled", onCheckButtonToggled, overwrite_check_button, key)
  settings.bind(key, overwrite_check_button, 'active', Gio.SettingsBindFlags.GET)
  optionsBox.add(overwrite_check_button)
  # --- End of tab --- add it to notebook
  pref_notebook.append_page(optionsBox, Gtk.Label(_('Daemon options')))
  # ------ Dialog construction is finished -------
  preferencesWindow.show_all()
  preferencesWindow.run()
  preferencesWindow.destroy()
  optionsSave()                     # Save daemon statrt options in config file
  menu_widget.set_sensitive(True)   # Enable menu item

def showOutput(menu_widget): # Display daemon output in dialogue window
  global origLANG
  global workLANG
  global daemonOutput
  menu_widget.set_sensitive(False)      # Disable menu item
  os.putenv('LANG',origLANG)            # Restore original LANG settings
  getDaemonOutput()
  os.putenv('LANG',workLANG)            # set back LANG settings for the main activities
  statusWindow = Gtk.Dialog()
  statusWindow.set_title(_('Yandex.Disk daemon output message'))
  statusWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(yandexDiskIcon))
  statusWindow.set_border_width(6)
  statusWindow.add_button(_('Close'),Gtk.ResponseType.CLOSE)
  textBox = Gtk.TextView()              # Create text-box for daemon output display
  textBox.get_buffer().set_text(daemonOutput)
  textBox.set_editable(False)
  statusWindow.get_content_area().add(textBox) # Put it inside the dialogue content area
  statusWindow.show_all()
  statusWindow.run()
  statusWindow.destroy()
  menu_widget.set_sensitive(True)    # Enable menu item

def renderMenu(): # Render initial menu (without any actual information)
  global menu_status
  global menu_used
  global menu_free
  global menu_YD_daemon_stop
  global menu_YD_daemon_start
  global widgetsList
  global pathsList
  global yandexDiskFolder
  menu = Gtk.Menu()           # Create menu
  menu_status = Gtk.MenuItem()
  menu_status.set_use_underline(False)
  menu_status.set_label('...')
  menu_status.connect("activate", showOutput)
  menu.append(menu_status)
  menu_used = Gtk.MenuItem()
  menu_used.set_use_underline(False)
  menu_used.set_sensitive(False)
  menu_used.set_label('...')
  menu.append(menu_used)
  menu_free = Gtk.MenuItem()
  menu_free.set_use_underline(False)
  menu_free.set_sensitive(False)
  menu_free.set_label('...')
  menu.append(menu_free)
  submenu_last = Gtk.Menu()   # Sub-menu: list of last synchronized
  widgetsList = []            # List of menu_last widgets to update their labels later
  pathsList = []              # List of files/folders in lastMenu items
  for i in range(0, 9):
    pathsList.append('...')   # Initialize file list
    widgetsList.append(Gtk.MenuItem.new_with_label('...'))  # Store widget ID
    widgetsList[i].set_use_underline(False)
    widgetsList[i].connect("activate", openLast, i)
    submenu_last.append(widgetsList[i])
  menu_last = Gtk.MenuItem(_('Last synchronized items'))
  menu_last.set_use_underline(False)
  menu_last.set_submenu(submenu_last)
  menu.append(menu_last)
  menu.append(Gtk.SeparatorMenuItem.new()) #-----separator--------
  menu_YD_daemon_start = Gtk.MenuItem(_('Start Yandex.Disk daemon'))
  menu_YD_daemon_start.set_use_underline(False)
  menu_YD_daemon_start.connect("activate", startDaemon)
  menu_YD_daemon_start.set_sensitive(False)
  menu.append(menu_YD_daemon_start)
  menu_YD_daemon_stop = Gtk.MenuItem(_('Stop Yandex.Disk daemon'))
  menu_YD_daemon_stop.set_use_underline(False)
  menu_YD_daemon_stop.connect("activate", stopDaemon)
  menu_YD_daemon_stop.set_sensitive(False)
  menu.append(menu_YD_daemon_stop)
  menu_open_YD_folder = Gtk.MenuItem(_('Open Yandex.Disk Folder'))
  menu_open_YD_folder.set_use_underline(False)
  menu_open_YD_folder.connect("activate", openPath, yandexDiskFolder)
  menu.append(menu_open_YD_folder)
  menu_open_YD_web = Gtk.MenuItem(_('Open Yandex.Disk on the web'))
  menu_open_YD_web.set_use_underline(False)
  menu_open_YD_web.connect("activate", openInBrowser, 'http://disk.yandex.ru')
  menu.append(menu_open_YD_web)
  menu.append(Gtk.SeparatorMenuItem.new()) #-----separator--------
  menu_preferences = Gtk.MenuItem(_('Preferences'))
  menu_preferences.set_use_underline(False)
  menu_preferences.connect("activate", openPreferences)
  menu.append(menu_preferences)
  menu_help = Gtk.MenuItem(_('Help'))
  menu_help.set_use_underline(False)
  menu_help.connect("activate", openInBrowser, 'http://help.yandex.ru/disk/')
  menu.append(menu_help)
  menu_about = Gtk.MenuItem(_('About'))
  menu_about.set_use_underline(False)
  menu_about.connect("activate", openAbout)
  menu.append(menu_about)
  menu.append(Gtk.SeparatorMenuItem.new()) #-----separator--------
  menu_quit = Gtk.MenuItem(_('Quit'))
  menu_quit.set_use_underline(False)
  menu_quit.connect("activate", quitApplication)
  menu.append(menu_quit)
  menu.show_all()
  return menu

def startDaemon(widget):
  # Try to start yandex-disk daemon and change the menu items sensitivity
  err = startYDdaemon()
  if err == '':
    updateStartStop(True)
  else:
    daemonErrorDialog(err)
    updateStartStop(False)

def stopDaemon(widget):
  stopYDdaemon()
  updateStartStop(False)

def checkDaemon(): # Checks that daemon process is running.
  # It should provide a correct response. Kills the daemon when it is running but not responding (HARON_CASE).
  global currentStatus
  currentStatus = 'none'
  try:
    msg = subprocess.check_output(['pgrep', '-x', 'yandex-disk'],universal_newlines=True)[ :-1]
  except:
    debugPrint("yandex-disk daemon is not running")
    return False
  debugPrint('yandex-disk daemon PID is: %s'%msg)
  if getDaemonOutput():  # Check for correct daemon response
    debugPrint('yandex-disk daemon is responding correctly.')
    parseDaemonOutput()  # Parse response to update currentStatus
    return True
  debugPrint('yandex-disk daemon is NOT responding!')
  try:                   # As it is not responding - try to kill all instances of daemon
    subprocess.check_call(['killall', 'yandex-disk'])
    debugPrint('yandex-disk daemon killed')
  except:
    debugPrint('yandex-disk daemon kill error')
  return False

def parseDaemonOutput(): # Parse the daemon output
  # Pre-formats status messages for menu
  global currentStatus
  global yandexDiskStatus
  global yandexDiskSpace1
  global yandexDiskSpace2
  global syncProgress
  global lastItems
  global daemonOutput
  # Look for synchronization progress
  lastPos = 0
  startPos = daemonOutput.find('ync progress: ')
  if startPos > 0:
    startPos += 14  # 14 is a length of 'ync progress: ' string
    lastPos = daemonOutput.find('\n',startPos)
    syncProgress = daemonOutput[startPos: lastPos]
  else:
    syncProgress = ''
  if daemonOutput != '':
    # Look for current core status (it is always presented in output)
    startPos = daemonOutput.find('core status: ',lastPos)+13  # 13 is len('core status: ')
    lastPos = daemonOutput.find('\n',startPos)
    currentStatus = daemonOutput[startPos: lastPos]
  else:
    currentStatus = 'none'
  # Look for total Yandex.Disk size
  startPos = daemonOutput.find('Total: ',lastPos)
  if startPos > 0:
    startPos += 7   # 7 is len('Total: ')
    lastPos = daemonOutput.find('\n',startPos)
    sTotal = daemonOutput[startPos: lastPos]
    ## If 'Total: ' was found then other information as also should be presented
    # Look for used Yandex.Disk size.
    startPos = daemonOutput.find('Used: ',lastPos)+6  # 6 is len('Used: ')
    lastPos = daemonOutput.find('\n',startPos)
    sUsed = daemonOutput[startPos: lastPos]
    # Look for free size on Yandex.Disk.
    startPos = daemonOutput.find('Available: ',lastPos)+11  # 11 is len('Available: ')
    lastPos = daemonOutput.find('\n',startPos)
    sAvailable = daemonOutput[startPos: lastPos]
    # Look for trash size of Yandex.Disk
    startPos = daemonOutput.find('Trash size: ',lastPos)+12  # 12 is len('Trash size: ')
    lastPos = daemonOutput.find('\n',startPos)
    sTrash = daemonOutput[startPos: lastPos]
  else: # When there is no Total: it is also other sizes are not presented
    sTotal = '...'
    sUsed = '...'
    sAvailable = '...'
    sTrash = '...'
  # Look for last synchronized items list
  startPos = daemonOutput.find('Last synchronized',lastPos)
  if startPos > 0:
    startPos = daemonOutput.find('\n',startPos)+1 # skip one line
    lastItems = daemonOutput[startPos: ] # save the rest
    # Don't split last synchronized list on individual lines/paths.
    # It is easer to do it in the same loop where menu is being updated (in updateMenuInfo()).
  else:
    lastItems = ''
  # Prepare and format information for menu
  yandexDiskStatus = _('Status: ') + (\
  _('Synchronized')         if currentStatus == 'idle' else \
  _('Sync.: ')+syncProgress if currentStatus == 'busy' else \
  _('Indexing')             if currentStatus == 'index' else \
  _('Paused')               if currentStatus == 'paused' else \
  _('Daemon stopped')       if currentStatus == 'none' else \
  _('Not connected')        if currentStatus == 'no internet access' else \
  _('Error')             ) #if currentStatus == 'error' or any other errors
  yandexDiskSpace1 = _('Used: ')+sUsed+'/'+sTotal
  yandexDiskSpace2 = _('Free: ')+sAvailable+_(', trash: ')+sTrash

def startYDdaemon(): # Execute 'yandex-disk start' and return '' if success or error message if not
  # ... but sometime it starts successfully with error message
  try:
    msg = subprocess.check_output(['yandex-disk', 'start'],universal_newlines=True)
    debugPrint('Start success, message: %s'%msg)
    return ''
  except subprocess.CalledProcessError as e:
    debugPrint('Start failed:%s'%e.output)
    if e.output == '':   # probably 'os: no file'
      return 'NOTINSTALLED'
    err = 'NONET' if e.output.find('Proxy')>0 else\
          'BADDAEMON' if e.output.find('daemon')>0 else\
          'NOCONFIG'
    return err

def stopYDdaemon(): # Execute 'yandex-disk stop'
  try:
    msg = subprocess.check_output(['yandex-disk','stop'],universal_newlines=True)
  except:
    msg = ''
  return (msg != '')

def updateMenuInfo(): # Update information in menu
  global widgetsList
  global pathsList
  global lastItems
  global yandexDiskStatus
  global yandexDiskSpace1
  global yandexDiskSpace2
  global accErrorPath
  global menu_status
  global menu_used
  global menu_free
  menu_status.set_label(yandexDiskStatus) # Update status data
  menu_used.set_label(yandexDiskSpace1)
  menu_free.set_label(yandexDiskSpace2)
  # --- Update last synchronized list ---
  endPos = 0
  for i in range(0, 9):
    # Find and get path in lastItems
    startPos = lastItems.find("'",endPos+2)
    endPos = lastItems.find("\n",startPos)
    if (startPos<0) or (endPos<0) or (startPos == endPos):
      lastLine = '...'
    else:
      lastLine = lastItems[startPos+1:endPos-1]
    pathsList[i] = lastLine   # Store path/file to have an ability to open it later
    if len(lastLine) > 50:    # Is path too long to be a menu label?
      # Shorten it: get 23 symbols from beginning, then '...', and 24 from end (50 total)
      lastLine = lastLine[:22]+'...'+lastLine[-25:]
    # Replace underscore to disable use_underline feature of GTK menu acceleration
    widgetsList[i].set_label(lastLine.replace('_',u"\u02CD"))
    # Change sensitivity of last menu item according to the path existence.
    if os.path.exists(os.path.join(yandexDiskFolder,pathsList[i])):
      widgetsList[i].set_sensitive(True)
    else:
      widgetsList[i].set_sensitive(False)

def updateStartStop(started): # Update daemon start and stop menu items availability
  global menu_YD_daemon_start
  global menu_YD_daemon_stop
  global menu_status
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
  global currentStatus
  global newStatus
  global lastStatus
  global watchTimer
  global timerTriggeredCount

  getDaemonOutput()     # Get the latest status data from daemon
  parseDaemonOutput()   # Parse it
  # Convert status to the internal presentation ['busy','idle','paused','none','error']
  if currentStatus == 'index':     # Don't handle 'index' status
    newStatus = lastStatus         # Assume that status is not changed
  elif currentStatus in ['busy','idle','paused','none']:
    newStatus = currentStatus
  else:  # Status in ['error', 'no internet access','failed to connect to daemon process','access error'...]
    newStatus = 'error'
  debugPrint('Event triggered by %s      status: %s -> %s'%('inotify' if triggeredBy_iNotifier else 'timer  ',lastStatus, newStatus))
  updateMenuInfo()                  # Update information in menu
  if lastStatus != newStatus:       # Handle status change
    updateIcon()                    # Update icon
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
    if lastStatus == 'none':        # Daemon was just started when 'none' changed to something else
      updateStartStop(True)         # Change menu sensitivity
      sendmessage(_('Yandex.Disk'), _('Yandex.Disk daemon is started'))
    lastStatus = newStatus          # remember new status
  # --- Handle timer delays ---
  if triggeredBy_iNotifier:         # True means that it is called by iNonifier
    stopTimer(watchTimer)           # Recreate timer.
    watchTimer = GLib.timeout_add_seconds(2, handleEvent, False) # Set delay at 2 sec after last call from iNotifier.
    timerTriggeredCount = 0         # reset counter as it was triggered not by time watcher
  else:
    if newStatus != 'busy':         # in 'busy' keep last update interval (2 sec.)
      if timerTriggeredCount < 9:   # increase interval up to 10 sec (2+8)
        stopTimer(watchTimer)       # Recreate timer.
        watchTimer = GLib.timeout_add_seconds(2 + timerTriggeredCount, handleEvent, False)
        timerTriggeredCount += 1    # Increase cunt to increase delay in next time
  return True                       # To continue activations by timer.

def updateIconTheme(): # Update paths to icons according to current theme
  global iconThemePath
  global ind
  global icon_busy
  global icon_idle
  global icon_pause
  global icon_error
  try:          # Read defaults from dconf Settings
    if settings.get_boolean("theme"):
      themeStyle = 'light'
    else:
      themeStyle = 'dark'
  except:
      themeStyle = 'dark'
  # --- Set appropriate paths to icons ---
  iconThemePath = os.path.join(installDir, 'icons', themeStyle )
  icon_busy =  os.path.join(iconThemePath, 'yd-busy1.png')
  icon_idle =  os.path.join(iconThemePath, 'yd-ind-idle.png')
  icon_pause = os.path.join(iconThemePath, 'yd-ind-pause.png')
  icon_error = os.path.join(iconThemePath, 'yd-ind-error.png')

def updateIcon(): # Change indicator icon according to the current status
  global newStatus
  global lastStatus
  global icon_busy
  global icon_idle
  global icon_pause
  global icon_error
  global iconAnimationTimer
  global seqNum
  global ind

  if newStatus == 'busy' and lastStatus != 'busy': # Just entered into 'busy' status
    ind.set_icon(icon_busy)         # Start icon animation
    seqNum = 1                      # Start animation from first icon
    iconAnimationTimer = GLib.timeout_add(777, iconAnimation, 'iconAnimation') # Create animation sequence timer
    return                          # there is nothing to do any more here
  if newStatus != 'busy' and iconAnimationTimer > 0:  # Not 'busy' and animation is running
    stopTimer(iconAnimationTimer)   # Stop icon animation
  # --- Set icon for non-animated statuses ---
  if newStatus == 'idle':
    ind.set_icon(icon_idle)
  elif newStatus == 'error':
    ind.set_icon(icon_error)
  else:                    # newStatus is 'none' or 'paused'
    ind.set_icon(icon_pause)

def iconAnimation(widget): # Changes busy icon by loop (triggered by iconAnimationTimer)
  global seqNum
  global ind
  global iconThemePath
  seqFile = 'yd-busy'+str(seqNum)+'.png'
  ind.set_icon(os.path.join(iconThemePath, seqFile))
  if seqNum < 5:         # 5 icons in loop (1-2-3-4-5-1-2-3...)
    seqNum += 1
  else:
    seqNum = 1
  return True            # True required to continue triggering by timer

def activateActions(): # Install/deinstall file extensions
  try:          # get settings
    activate = settings.get_boolean("fmextensions")
  except:
    activate = False
  # --- Actions for nautilus ---
  ret = subprocess.call(["dpkg -s nautilus>/dev/null 2>&1"], shell = True)
  debugPrint("Nautilus installed: %s"%str(ret == 0))
  if ret == 0:
    ver = subprocess.check_output(["lsb_release -r | sed -n '1{s/[^0-9]//g;p;q}'"], shell = True)
    if ver!='' and int(ver) < 1210:
      nautilusPath = ".gnome2/nautilus-scripts/"
    else:
      nautilusPath = ".local/share/nautilus/scripts"
    debugPrint(nautilusPath)
    if activate:  # Install actions for Nautilus
      copyFile(os.path.join(installDir,"fm-actions/Nautilus_Nemo/publish"), os.path.join(userHome,nautilusPath,"Опубликовать через Yandex.Disk"))
      copyFile(os.path.join(installDir,"fm-actions/Nautilus_Nemo/unpublish"), os.path.join(userHome,nautilusPath,"Убрать из публикации через Yandex.disk"))
    else:         # Remove actions for Nautilus
      deleteFile(os.path.join(userHome,nautilusPath,"Опубликовать через Yandex.Disk"))
      deleteFile(os.path.join(userHome,nautilusPath,"Убрать из публикации через Yandex.disk"))
  # --- Actions for Nemo ---
  ret = subprocess.call(["dpkg -s nemo>/dev/null 2>&1"], shell = True)
  debugPrint("Nemo installed: %s"%str(ret == 0))
  if ret == 0:
    if activate:  # Install actions for Nemo
      copyFile(os.path.join(installDir,"fm-actions/Nautilus_Nemo/publish"), os.path.join(userHome,".gnome2/nemo-scripts","Опубликовать через Yandex.Disk"))
      copyFile(os.path.join(installDir,"fm-actions/Nautilus_Nemo/unpublish"), os.path.join(userHome,".gnome2/nemo-scripts","Убрать из публикации через Yandex.disk"))
    else:         # Remove actions for Nemo
      deleteFile(os.path.join(userHome,".gnome2/nemo-scripts", "Опубликовать через Yandex.Disk"))
      deleteFile(os.path.join(userHome,".gnome2/nemo-scripts", "Убрать из публикации через Yandex.disk"))
  # --- Actions for Thunar ---
  ret = subprocess.call(["dpkg -s thunar>/dev/null 2>&1"], shell = True)
  debugPrint("Thunar installed: %s"%str(ret == 0))
  if ret == 0:
    if activate:  # Install actions for Thunar
      if subprocess.call(["grep 'yandex-disk publish' "+os.path.join(userHome,".config/Thunar/uca.xml")+">/dev/null 2>&1"], shell=True) != 0:
        subprocess.call(["sed", "-i", 's/<\/actions>/<action><icon>folder-publicshare<\/icon><name>Публикация через Yandex.Disk<\/name><command>yandex-disk publish %f | xclip -filter -selection clipboard; zenity --info --window-icon=\/opt\/yd-tools\/icons\/yd-128.png --title="Yandex.Disk" --ok-label="Закрыть" --text="Ссылка на файл: %f скопирована в буфер обмена."<\/command><description><\/description><patterns>*<\/patterns><directories\/><audio-files\/><image-files\/><other-files\/><text-files\/><video-files\/><\/action><\/actions>/g', os.path.join(userHome,".config/Thunar/uca.xml") ])
      if subprocess.call(["grep 'yandex-disk unpublish' "+os.path.join(userHome,".config/Thunar/uca.xml")+">/dev/null 2>&1"], shell=True) != 0:
        subprocess.call(["sed", "-i", 's/<\/actions>/<action><icon>folder<\/icon><name>Убрать из публикации через Yandex.disk<\/name><command>zenity --info --window-icon=\/opt\/yd-tools\/icons\/yd-128_g.png --ok-label="Закрыть" --title="Yandex.Disk" --text="Убрать из публикации через Yandex.disk: \`yandex-disk unpublish %f\`"<\/command><description><\/description><patterns>*<\/patterns><directories\/><audio-files\/><image-files\/><other-files\/><text-files\/><video-files\/><\/action><\/actions>/g', os.path.join(userHome,".config/Thunar/uca.xml")])
    else:         # Remove actions for Thunar
      subprocess.call(["sed", "-i", "s/<action><icon>.*<\/icon><name>Публикация через Yandex.Disk.*<\/action>//", os.path.join(userHome,".config/Thunar/uca.xml") ])
      subprocess.call(["sed", "-i", "s/<action><icon>.*<\/icon><name>Убрать из публикации через Yandex.disk.*<\/action>//", os.path.join(userHome,".config/Thunar/uca.xml") ])
  # Actions for Dolphin
  ret = subprocess.call(["dpkg -s dolphin>/dev/null 2>&1"], shell = True)
  debugPrint("Dolphin installed: %s"%str(ret == 0))
  if ret == 0:
    if activate:  # Install actions for Dolphin
      copyFile(os.path.join(installDir,"fm-actions/Dolphin/publish.desktop"), os.path.join(userHome,".kde/share/kde4/services/publish.desktop"))
      copyFile(os.path.join(installDir,"fm-actions/Dolphin/unpublish.desktop"), os.path.join(userHome,".kde/share/kde4/services/unpublish.desktop"))
    else:         # Remove actions for Dolphin
      deleteFile(os.path.join(userHome,".kde/share/kde4/services/publish.desktop"))
      deleteFile(os.path.join(userHome,".kde/share/kde4/services/unpublish.desktop"))

def optionsSave(): # Update daemon config file according to the configuration settings
  global daemonConfig
  roExist = False
  ovExist = False
  roVal = settings.get_boolean('optionreadonly')
  ovVal = settings.get_boolean('optionoverwrite')
  try:
    cfgFile = open(daemonConfig, 'rt')
  except:
    debugPrint('CFG File open error')
  else:   # Open new temporary file in text mode for write ad keep it after close
    newFile = tempfile.NamedTemporaryFile(mode='wt', delete=False)
    for line in cfgFile:
      if line.startswith('read-only='):
        roExist = True
        if not roVal:
          continue
      elif line.startswith('overwrite='):
        ovExist = True
        if not (roVal and ovVal) :
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

def readConfig(): # Update settings according to daemon config file and get yandex.disk folder path.
  global daemonConfig
  global yandexDiskFolder
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
        if line[pos] == '"' :
          pos+=1
          yandexDiskFolder = line[pos: line.find('"',pos)]
        else:
          yandexDiskFolder = line[pos: line.find('/n',pos)]
        yandexDiskFolder = yandexDiskFolder.decode('utf-8')  # Decode required for python 2.7 and not required for python 3.0 and above
        debugPrint('Config: yandexDiskFolder = %s'%yandexDiskFolder)
    cfgFile.close()
    settings.set_boolean('optionreadonly', roVal)
    settings.set_boolean('optionoverwrite', ovVal)
    return (yandexDiskFolder != '')

def getDaemonOutput():
  global daemonOutput
  try:
    daemonOutput = subprocess.check_output(['yandex-disk', 'status'],universal_newlines=True)
  except:
    daemonOutput = ''
  daemonOutput = daemonOutput.decode('utf-8') # Decode required for python 2.7 and not required for python 3.0 and above
  #debugPrint('output = %s'%daemonOutput)
  return (daemonOutput != '')

###################### MAIN LOOP #########################
if __name__ == '__main__':
  ### Application variables and settings ###
  appVersion = '1.2.3'
  appName = 'yandex-disk-indicator'
  installDir = os.path.dirname(os.path.realpath(__file__))
  userHome = os.getenv("HOME")
  # Define .desktop files locations for auto-start facility
  autoStartSource = os.path.join(installDir,'Yandex.Disk-indicator.desktop')
  autoStartDestination = os.path.join(userHome, '.config', 'autostart', 'Yandex.Disk-indicator.desktop')
  autoStartSource1 = os.path.join(installDir,'Yandex.Disk.desktop')
  autoStartDestination1 = os.path.join(userHome, '.config', 'autostart', 'Yandex.Disk.desktop')
  # Yandex.Disk configuration file path
  daemonConfig = os.path.join(userHome, '.config', 'yandex-disk', 'config.cfg')
  # Restore and set LANG environment for daemon output (it must be 'en' for correct parsing)
  origLANG = os.getenv('LANG')
  workLANG = 'en_US.UTF-8'
  os.putenv('LANG',workLANG)
  ### Configuration settings ###
  try:
    settings = Gio.Settings.new("apps."+appName)
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
  try:    # Update auto-start settings according to actual files existence in ~/.config/autostart
    settings.set_boolean('autostart',os.path.isfile(autoStartDestination))
    settings.set_boolean('autostartdaemon',os.path.isfile(autoStartDestination1))
  except:
    pass
  ### Localization ###
  debugPrint("Current Locale : %s" % str(locale.getlocale()))
  try:            # Try to load translation
    appTranslate = gettext.translation(appName, '/usr/share/locale', fallback = True)
    _ = appTranslate.ugettext   #ugettext for python2.7 and gettext for python3
  except:
    _ = str
  ### Activate FM actions according to settings if lock file not exists (probably it is a first run)
  lockFileName = '/tmp/'+appName+'.lock'
  if not os.path.isfile(lockFileName):
    activateActions()
  ### Check for already running instance of the indicator application ###
  try:
    lockFile = open(lockFileName,'w')                       # Open lock file for write
    fcntl.flock(lockFile, fcntl.LOCK_EX|fcntl.LOCK_NB)      # Try to acquire exclusive lock
  except: # File is already locked
    sys.exit(_('Yandex.Disk Indicator instance already running\n(file /tmp/%s.lock is locked by another process)')%appName)
  lockFile.write('%d\n'%os.getpid())
  lockFile.flush()
  ### Yandex.Disk daemon ###
  if checkDaemon():             # Daemon is running now ?
    readConfig()                # Read Yandex.Disk config file
  else:                         # Daemon is not running now
    if not os.path.exists('/usr/bin/yandex-disk'):
      daemonErrorDialog('NOTINSTALLED')
      appExit()               # Daemon is not installed. Exit right now.
    if not readConfig():      # Read Yandex.Disk config file
      if daemonErrorDialog('NOCONFIG') != 0:
        appExit()             # User hasn't configured daemon. Exit right now.
    if settings.get_boolean("startonstart"):
        err = startYDdaemon() # Try to start it
        if err != '':
          if daemonErrorDialog(err) != 0:
            appExit()         # Something wrong. It's no way to continue. Exit right now.
  lastStatus = currentStatus  # set initial stored status
  newStatus = currentStatus   # set initial current status
  ### On-screen notifications ###
  Notify.init(appName)        # Initialize notification engine
  notifier = Notify.Notification()
  ### Application Indicator ###
  ## Icons ##
  yandexDiskIcon = os.path.join(installDir,'icons', 'yd-128.png')   # Big icon
  updateIconTheme()           # Define the rest icons paths
  iconAnimationTimer = 0      # Define the icon animation timer variable
  ## Indicator creation ##
  ind = appindicator.Indicator.new("yandex-disk", icon_pause, appindicator.IndicatorCategory.APPLICATION_STATUS)
  ind.set_status (appindicator.IndicatorStatus.ACTIVE)
  ind.set_menu(renderMenu())  # Prepare and attach menu to indicator
  updateIcon()                # Update icon according to current status
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
  watchManager = pyinotify.WatchManager()       # Create watch manager
  iNotifier = pyinotify.Notifier(watchManager, EventHandler(), timeout=0.5) # Create PyiNotifier
  watchManager.add_watch(os.path.join(yandexDiskFolder,'.sync/cli.log'), pyinotify.IN_MODIFY, rec = False)  # Add watch
  iNotifierTimer = GLib.timeout_add(700, iNotifyHandler)  # Call iNotifier handler every 0.7 seconds.
  Gtk.main()                  # Start GTK Main loop
