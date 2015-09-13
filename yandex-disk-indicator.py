#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Yandex.Disk indicator
appVer = '1.5.1'
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
from gi.repository import AppIndicator3 as appIndicator
from gi.repository import GdkPixbuf
from gi.repository import Notify
from shutil import copy as fileCopy
from collections import OrderedDict as ordDict
from webbrowser import open_new as openNewBrowser
import os, sys, subprocess, pyinotify, fcntl, gettext, datetime

class OrderedDict(ordDict):  # Redefine OrderdDict class with working setdefault
  def setdefault(self, key, val):  # Redefine not working setdefault method of OreredDict class
    try:
      return self[key]
    except:
      self[key] = val
      return val

class CVal(object):
# Class to work with value that can be None, scalar value or list of values depending
# of number of elementary values added within it. 

  def __init__(self, initialValue=None):
    self.val = initialValue   # store initial value
    self.index = None

  def get(self):  # It just returns the current value of cVal
    return self.val

  def add(self, value):   # Add value without any convertion
    if isinstance(self.val, list):  # Is it third, fourth ... value?
      self.val.append(value)        # Just append new value to list
    elif self.val == None:          # Is it first value?
      self.val = value              # Just store value
    else:                           # It is the second value.
      self.val = [self.val, value]  # Convert scalar value to list of values.
    return self.val

  def __iter__(self):   # cVal iterator object initialization
    if isinstance(self.val, list):  # Is CVal a list?
      self.index = -1
    elif self.val == None:          # Is CVal not defined?
      self.index = None
    else:                           # CVal is scalar type.
      self.index = -2
    return self

  def __next__(self):   # cVal iterator support
    if self.index == None:            # Is CVal not defined?
      raise StopIteration             # Stop iterations
    self.index += 1
    if self.index >= 0:               # Is CVal a list?
      if self.index < len(self.val):  # Is there a next element in list?
        return self.val[self.index]
      else:                           # There is no more elements in list.
        self.index = None
        raise StopIteration           # Stop iterations
    else:                             # CVal has scalar type.
      self.index = None               # Remember that there is no more iterations posible
      return self.val

class Config(OrderedDict):
  def __init__(self, filename, load=True):
    OrderedDict.__init__(self)
    self.fileName = filename
    if load:
      self.load()

  def decode(self, value):    # Convert string to value before store it
    if value.lower() in ['true', 'yes', 'y']:   # Convert Boolean
      value = True
    elif value.lower() in ['false', 'no', 'n']:
      value = False
    return value
  
  def load(self):
    """
    Reads config file to dictionalry (OrderedDict)
    Compatible with yandex-disk config.cfg file syntax.
    Config file conains key=value rows
    Key can be quoted or not.
    Value can be one item or list of comma-separated items
    Each value item can be quoted or not
    When value is a single item then key:value item in dictionalry
    In case list of items it returns key:[value, value,...] item.
    """

    def parse(row):                                 # Search values behind the '=' symbol
      val = CVal()
      lp = 0                                        # Set last position on '=' symbol
      while True:
        q1 = row.find('"', lp+1)                    # Try to find opening quote
        q2 = row.find(',', lp+1)                    # Try to find delimiter
        if q2 > 0 and (q1 > q2 or q1 < 0):          # ',' was found and '"' is after ',' or
                                                    # or only ',' was found ('"' was not found)
          if row[lp] == '"':                        # ... after '"'
            lp = q2                                 # move to ',' that was found
            continue                                # Restart search
          else:                                     # row[lp] in ['=', ',']
            val.add(self.decode(row[lp+1: q2].strip()))  # Get value between last symbol and ','
            lp = q2                                 # move to ',' that was found
        elif q1 > 0:                                # Opening '"' was found (',' was not found)
          if row[lp] in [',', '=']:                 # ... after '=' or ','
            q2 = row.find('"', q1+1)                # Try to find closing quote
            if q2 > 0:                              # Closing quote found
              val.add(self.decode(row[q1+1: q2]))   # Get value between quotes (don't stip it)
              lp = q2                               # move to ending '"'
            else:                                   # ERROR: no ending quote found for opening one
              break                                 # Stop search.
          else:                                     # ERROR: opening '"' was found after closing '"'
            break                                   # Stop search.
        else:                                       # Neither Opening quote nor delimiter was found
          if row[lp] == '"':                        # ... after closing '"'
            break                                   # There is no (more) values, stop search
          else:                                     # ... after '=' or ','
            val.add(self.decode(row[lp+1: -1].strip()))  # Get value between last and string end
            break                                   # There is no (more) values, stop search
      return val.get()
  
    try:
      with open(self.fileName) as cf:
        for row in cf:                 # Parse lines
          if row[0] != '#':            # Ignore comments
            p = row.find('=')
            if p > 0:                  # '=' symbol was found
              key = (row[:p]).strip()  # Remember key name
              if key[0] == '"':
                if key[-1] == '"':
                  key = key[1: -1]     # Remove quotes adaund key
                else:
                  continue             # Skip row with wrong key
              if key:                  # When key is not empty
                val = parse(row[p:])   # Get value(s) form the rest of row
                if val != None:        # Is there at least one value were found?
                  self[key] = val      # Yes! Great! Save it.
      debug.print('Config read: %s' % self.fileName)
      return True
    except:
      debug.print('Config file read error: %s' % self.fileName)
      return False
    
  def encode(self, val):      # Convert value to string before save it
    if isinstance(val, bool):  # Treat Boolean
      val = self.boolval[0] if val else self.boolval[1]
    if self.usequotes:
      val = '"' + val + '"'
    return val                 # Put value within quotes

  def save(self, boolval=['yes', 'no'], usequotes=True):      # Write setting to config file
    self.usequotes = usequotes
    self.boolval = boolval
    try:
      with open(self.fileName, 'wt') as cf:
        for key, value in self.items():
          res = key + '='             # Start composing config row 
          for val in CVal(value):     # Iterate through the value 
            res += self.encode(val) + ','  # Collect values in comma separated list
          if res[-1] == ',':
            res = res[: -1]           # Remove last comma
          cf.write(res + '\n')        # Write resulting string in file
      debug.print('Config written: %s' % self.fileName)
      return True
    except:
      debug.print('Config file write error: %s' % self.fileName)
      return False

class Debug(object):  # Debuger class
  def __init__(self, verboseOutput=True): 
    self.switch(verboseOutput)

  def switch(self, verboseOutput):  # Change debug mode
    if verboseOutput:
      self.print = self.out
    else:
      self.print = lambda t: None

  def out(self, text):  # Debug output function
    try:
      print('%s: %s' % (datetime.datetime.now().strftime("%M:%S.%f"), text))
    except:
      pass

class Notification(object):  # On-screen notifications
  def __init__(self, app, mode):
    Notify.init(app)        # Initialize notification engine
    self.notifier = Notify.Notification()
    self.switch(mode)

  def switch(self, mode):   # Change show mode
    if mode:
      self.send = self.message
    else:
      self.send = lambda t, m: None
      
  def message(self, title, message):
    global logo
    debug.print('Message :%s' % message)
    self.notifier.update(title, message, logo)    # Update notification
    self.notifier.show()                                    # Display new notification

class INotify(object):  # File change watcher
  def __init__(self, path, handler, pram):
    class EH(pyinotify.ProcessEvent):   # Event handler class for iNotifier
      def process_IN_MODIFY(self, event):
        handler(pram)
    watchMngr = pyinotify.WatchManager()                                   # Create watch manager
    self.iNotifier = pyinotify.Notifier(watchMngr, EH(), timeout=0.5)   # Create PyiNotifier
    watchMngr.add_watch(path, pyinotify.IN_MODIFY, rec = False)                    # Add watch
    self.timer = GLib.timeout_add(700, self.handler)  # Call iNotifier handler every .7 seconds

  def handler(self):  # iNotify working routine (called by timer)
    global iNotifier
    while self.iNotifier.check_events():
      self.iNotifier.read_events()
      self.iNotifier.process_events()
    return True

class Preferences(Gtk.Dialog):          # Preferences Window
  def __init__(self, widget):
    # Preferences Window routine
    global appConfig, daemon
    widget.set_sensitive(False)          # Disable menu item to avoid multiple windows creation
    # Create Preferences window
    Gtk.Dialog.__init__(self, _('Yandex.Disk-indicator and Yandex.Disk preferences'), flags=1)
    self.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
    self.set_border_width(6)
    self.add_button(_('Close'), Gtk.ResponseType.CLOSE)
    pref_notebook = Gtk.Notebook()            # Create notebook for indicator and daemon options
    self.get_content_area().add(pref_notebook)  # Put it inside the dialog content area
    # --- Indicator preferences tab ---
    preferencesBox = Gtk.VBox(spacing=5)
    key = 'autostart'                         # Auto-start indicator on system start-up
    сheckButton = Gtk.CheckButton(
                               _('Start Yandex.Disk indicator when you start your computer'))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    preferencesBox.add(сheckButton)
    key = 'startonstart'                      # Start daemon on indicator start
    сheckButton = Gtk.CheckButton(_('Start Yandex.Disk daemon when indicator is starting'))
    сheckButton.set_tooltip_text(_("When daemon was not started before."))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    preferencesBox.add(сheckButton)
    key = 'stoponexit'                        # Stop daemon on exit
    сheckButton = Gtk.CheckButton(_('Stop Yandex.Disk daemon on closing of indicator'))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    preferencesBox.add(сheckButton)
    key = 'notifications'                     # Notifications
    сheckButton = Gtk.CheckButton(_('Show on-screen notifications'))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    preferencesBox.add(сheckButton)
    key = 'theme'                             # Theme
    сheckButton = Gtk.CheckButton(_('Prefer light icon theme'))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    preferencesBox.add(сheckButton)
    key = 'fmextensions'                      # Activate file-manager extensions
    сheckButton = Gtk.CheckButton(_('Activate file manager extensions'))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    preferencesBox.add(сheckButton)
    # --- End of Indicator preferences tab --- add it to notebook
    pref_notebook.append_page(preferencesBox, Gtk.Label(_('Indicator settings')))
    # --- Daemon start options tab ---
    optionsBox = Gtk.VBox(spacing=5)
    key = 'autostartdaemon'                   # Auto-start daemon on system start-up
    сheckButton = Gtk.CheckButton(_('Start Yandex.Disk daemon when you start your computer'))
    сheckButton.set_active(appConfig[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    optionsBox.add(сheckButton)
    frame = Gtk.Frame()
    frame.set_label(_("NOTE! You have to reload daemon to activate following settings"))
    frame.set_border_width(6)
    optionsBox.add(frame)
    framedBox = Gtk.VBox(homogeneous=True, spacing=5)
    frame.add(framedBox)
    key = 'read-only'                         # Option Read-Only    # daemon config
    сheckButton = Gtk.CheckButton(
                    _('Read-Only: Do not upload locally changed files to Yandex.Disk'))
    сheckButton.set_tooltip_text(
      _("Locally changed files will be renamed if a newer version of this file appear in " +
        "Yandex.Disk."))
    сheckButton.set_active(daemon.config[key])
    сheckButton.connect("toggled", self.onButtonToggled, сheckButton, key)
    framedBox.add(сheckButton)
    key = 'overwrite'                         # Option Overwrite    # daemon config
    self.overwrite = Gtk.CheckButton(_('Overwrite locally changed files by files' +
                                       ' from Yandex.Disk (in read-only mode)'))
    self.overwrite.set_tooltip_text(
      _("Locally changed files will be overwritten if a newer version of this file appear " +
        "in Yandex.Disk."))
    self.overwrite.set_active(daemon.config[key])
    self.overwrite.set_sensitive(daemon.config['read-only'])
    self.overwrite.connect("toggled", self.onButtonToggled, self.overwrite, key)
    framedBox.add(self.overwrite)
    # Excude folders list
    exListButton = Gtk.Button(_('Excluded folders List'))
    exListButton.set_tooltip_text(_("Folders in the list will not be synchronized."))
    upd = [False]
    exListButton.connect("clicked", self.excludeDirsList, self)
    framedBox.add(exListButton)
    # --- End of Daemon start options tab --- add it to notebook
    pref_notebook.append_page(optionsBox, Gtk.Label(_('Daemon options')))
    self.show_all()
    self.appCfgUpdate = False
    self.daemonCfgUpdate = False
    self.run()
    if self.daemonCfgUpdate:
      daemon.config.save()                        # Save daemon options in config file
    if self.appCfgUpdate:
      appConfig.save()                 # Save app appConfig
    widget.set_sensitive(True)           # Enable menu item
    self.destroy()
    
  def onButtonToggled(self, widget, button, key):  # Handle clicks on check-buttons
    global notificationSetting, appConfig, overwrite_check_button, daemon, icon
    toggleState = button.get_active()
    if key in ['read-only', 'overwrite']:
      daemon.config[key] = toggleState             # Update daemon config
      self.daemonCfgUpdate = True
    else:
      appConfig[key] = toggleState                # Update application config
      self.appCfgUpdate = True
    debug.print('Togged: %s  val: %s' % (key, str(toggleState)))
    if key == 'theme':
      icon.updateTheme()                           # Update themeStyle
      icon.update()                                # Update current icon
    elif key == 'notifications':
      notify.switch(toggleState)                  # Update notification object
    elif key == 'autostartdaemon':
      if toggleState:
        copyFile(autoStartSource1, autoStartDestination1)
        notify.send(_('Yandex.Disk daemon'), _('Auto-start ON'))
      else:
        deleteFile(autoStartDestination1)
        notify.send(_('Yandex.Disk daemon'), _('Auto-start OFF'))
    elif key == 'autostart':
      if toggleState:
        copyFile(autoStartSource, autoStartDestination)
        notify.send(_('Yandex.Disk Indicator'), _('Auto-start ON'))
      else:
        deleteFile(autoStartDestination)
        notify.send(_('Yandex.Disk Indicator'), _('Auto-start OFF'))
    elif key == 'fmextensions':
      activateActions()
    elif key == 'read-only':
      self.overwrite.set_sensitive(toggleState)

  class excludeDirsList(Gtk.Dialog):    # Excluded list dialogue class
    def __init__(self, widget, parent):
      global daemon
      self.parent = parent
      Gtk.Dialog.__init__(self, title=_('Folders that are excluded from synchronization'),
                          parent=parent, flags=1)
      self.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
      self.set_border_width(6)
      self.add_button(_('Add catalogue'),
                      Gtk.ResponseType.APPLY).connect("clicked", self.folderChoiserDialog, self)
      self.add_button(_('Remove selected'),
                      Gtk.ResponseType.REJECT).connect("clicked", self.deleteSelected)
      self.add_button(_('Close'),
                      Gtk.ResponseType.CLOSE).connect("clicked", self.exitFromDialog)
      self.excludeList = Gtk.ListStore(bool , str)
      view = Gtk.TreeView(model=self.excludeList)
      render = Gtk.CellRendererToggle()
      render.connect("toggled", self.lineToggled)
      view.append_column(Gtk.TreeViewColumn(" ", render, active=0))
      view.append_column(Gtk.TreeViewColumn(_('Path'), Gtk.CellRendererText(), text=1))
      self.get_content_area().add(view)
      # Populate list with paths from "exclude-dirs" property of daemon configuration
      for val in CVal(daemon.config.get('exclude-dirs', None)):
        self.excludeList.append([False, val])
      self.show_all()

    def exitFromDialog(self, widget):  # Save list from dialogue to "exclude-dirs" property
      global daemonConfig
      exList = CVal()
      listIter = self.excludeList.get_iter_first()
      while listIter != None:
        exList.add(self.excludeList.get(listIter, 1)[0])  # Store path value from dialogue list row
        listIter = self.excludeList.iter_next(listIter)
      daemon.config['exclude-dirs'] = exList.get()         # Save collected value
      self.destroy()                                      # Close dialogue

    def lineToggled(self, widget, path):  # Line click handler, it switch row selection
      self.excludeList[path][0] = not self.excludeList[path][0]

    def deleteSelected(self, widget):  # Remove selected rows from list
      listIiter = self.excludeList.get_iter_first()
      while listIiter != None and self.excludeList.iter_is_valid(listIiter):
        if self.excludeList.get(listIiter, 0)[0]:
          self.excludeList.remove(listIiter)
          self.parent.daemonCfgUpdate = True
        else:
          listIiter = self.excludeList.iter_next(listIiter)

    def folderChoiserDialog(self, widget, parent):  # Add new path to list via FileChooserDialog
      global daemon
      dialog = Gtk.FileChooserDialog(_('Select catalogue to add to list'), parent,
                                   Gtk.FileChooserAction.SELECT_FOLDER,
                                   (_('Close'), Gtk.ResponseType.CANCEL,
                                    _('Select'), Gtk.ResponseType.ACCEPT))
      dialog.set_default_response(Gtk.ResponseType.CANCEL)
      dialog.set_current_folder(daemon.yandexDiskFolder)
      if dialog.run() == Gtk.ResponseType.ACCEPT:
        res = os.path.relpath(dialog.get_filename(), start=daemon.yandexDiskFolder)
        self.excludeList.append([False, res])
        self.parent.daemonCfgUpdate = True
      dialog.destroy()

class DConfig(Config):  # redefined class for daemon config 
  def save(self):  # Update daemon config file according to the configuration appConfig
    fileConfig = Config(self.fileName, load=False)
    for key, val in self.items():
      fileConfig[key] = val
    ro = fileConfig.pop('read-only', False)
    if ro:
      fileConfig['read-only'] = ''
    if fileConfig.pop('overwrite', False) and ro:
      fileConfig['overwrite'] = ''
    exList = fileConfig.pop('exclude-dirs', None)
    if exList != None:
      fileConfig['exclude-dirs'] = exList
    fileConfig.save()

  def load(self):  # Get daemon appConfig from its config file
    if super(DConfig, self).load():
      self['read-only'] = (self.get('read-only', False) == '')
      self['overwrite'] = (self.get('overwrite', False) == '')
      self['exclude-dirs'] = self.get('exclude-dirs', None)
      return True
    else:
      return False 

class YDDaemon(object):
  def __init__(self):           # Check that daemon installed, configured and started 
    if not os.path.exists('/usr/bin/yandex-disk'):
      self.ErrorDialog('NOTINSTALLED')
      appExit()                    # Daemon is not installed. Exit right now.
    self.configFile = os.path.join(userHome, '.config', 'yandex-disk', 'config.cfg')
    self.config = DConfig(self.configFile, load=False)
    while not self.config.load():  # Try to read Yandex.Disk configuration file
      if self.errorDialog('NOCONFIG') != 0:
        appExit()                  # User hasn't configured daemon. Exit right now.
    self.yandexDiskFolder = self.config.get('dir', '')
    while not self.getOutput():    # Check for correct daemon response and check that it is running
      try:                         # Try to find daemon running process
        msg = subprocess.check_output(['pgrep', '-x', 'yandex-disk'], universal_newlines=True)[: -1]
        debug.print('yandex-disk daemon is running but NOT responding!')
        # Kills the daemon(s) when it is running but not responding (HARON_CASE).
        try:                       # Try to kill all instances of daemon
          subprocess.check_call(['killall', 'yandex-disk'])
          debug.print('yandex-disk daemon(s) killed')
          msg = ''
        except:
          debug.print('yandex-disk daemon kill error')
          self.errorDialog('')
          appExit()                # nonconvertible error - exit
      except:
        debug.print("yandex-disk daemon is not running")
        msg = ''
      if msg == '' and not appConfig["startonstart"]:
        break               # Daemon is not started and should not be started
      else:
        err = self.start()      # Try to start it
        if err != '':
          if self.errorDialog(err) != 0:
            appExit()              # Something wrong. It's no way to continue. Exit right now.
          else:
            break           # Daemon was not started but user decided to start indicator anyway
      # here we have started daemon. Try to check it's output (in while loop)
    else:  # while
      debug.print('yandex-disk daemon is installed, configured and responding.')
    self.status = 'none'
    self.lastStatus = 'idle'         # fallback status for "index" status substitution at start time
    self.lastBuf = ''
    self.parseOutput()              # to update all status fields
    self.lastStatus = self.status
    self.lastBuf = '*'              # to be shure that self.lastItemsChanged = True on next time

  def getOutput(self):          # Get result of 'yandex-disk status' 
    try:    self.output = subprocess.check_output(['yandex-disk', 'status'], universal_newlines=True)
    except: self.output = ''     # daemon is not running or bad
    #debug.print('output = %s' % daemonOutput)
    return (self.output != '')

  def parseOutput(self):        # Parse the daemon output
    # Look for synchronization progress
    lastPos = 0
    startPos = self.output.find('ync progress: ')
    if startPos > 0:
      startPos += 14                         # 14 is a length of 'ync progress: ' string
      lastPos = self.output.find('\n', startPos)
      self.syncProgress = self.output[startPos: lastPos]
    else:
      self.syncProgress = ''
    # Look for current core status (it is always presented in output)
    self.lastStatus = self.status
    if self.output != '':
      startPos = self.output.find('core status: ', lastPos) + 13  # 13 is len('core status: '
      lastPos = self.output.find('\n', startPos)
      status = self.output[startPos: lastPos]
      if status == 'index':          # Don't handle index status
        status = self.lastStatus     # keep last status
      if status == 'no internet access':
        status = 'no_net'
      self.status = status if status in ['busy', 'idle', 'paused', 'none', 'no_net'] else 'error'
      # Status 'error' covers 'error', 'failed to connect to daemon process' and other messages...
    else:
      self.status = 'none'
    # Look for total Yandex.Disk size
    startPos = self.output.find('Total: ', lastPos)
    if startPos > 0:
      startPos += 7                         # 7 is len('Total: ')
      lastPos = self.output.find('\n', startPos)
      self.sTotal = self.output[startPos: lastPos]
      ## If 'Total: ' was found then other information as also should be presented
      # Look for used size                  # 6 is len('Used: ')
      startPos = self.output.find('Used: ', lastPos) + 6
      lastPos = self.output.find('\n', startPos)
      self.sUsed = self.output[startPos: lastPos]
      # Look for free size                  # 11 is len('Available: ')
      startPos = self.output.find('Available: ', lastPos) + 11
      lastPos = self.output.find('\n', startPos)
      self.sFree = self.output[startPos: lastPos]
      # Look for trash size                 # 12 is len('Trash size: ')
      startPos = self.output.find('Trash size: ', lastPos) + 12
      lastPos = self.output.find('\n', startPos)
      self.sTrash = self.output[startPos: lastPos]
    else:  # When there is no Total: then other sizes are not presented too
      self.sTotal = '...'
      self.sUsed = '...'
      self.sFree = '...'
      self.sTrash = '...'
    # Look for last synchronized items list
    startPos = self.output.find('Last synchronized', lastPos)
    if startPos > 0:                        # skip one line
      startPos = self.output.find('\n', startPos) + 1
      buf = self.output[startPos: ]        # save the rest
    else:
      buf = ''
    self.lastItemsChanged = (self.lastBuf != buf)   # check for changes in the list
    if self.lastItemsChanged:
      self.lastBuf = buf
      self.lastItems = []                              # clear list of file paths
      for listLine in buf.splitlines():
        startPos = listLine.find(": '")           # Find file path in the line
        if (startPos > 0):                        # File path was found
          filePath = listLine[startPos + 3: - 1]  # Get relative file path (skip quotes)
          self.lastItems.append(filePath)         # Store full file path

  def updateStatus(self):       # Get daemon output and update all daemon YDDaemon status variables 
    self.getOutput()
    self.parseOutput()

  def errorDialog(self, err):   # Show error messages according to the error
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
    dialog.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
    response = dialog.run()
    dialog.destroy()
    if (err == 'NOCONFIG') and (response == Gtk.ResponseType.OK):  # Launch Set-up utility
      debug.print('starting configuration utility: %s' % os.path.join(installDir, 'ya-setup'))
      retCode = subprocess.call([os.path.join(installDir,'ya-setup')])
    else:
      retCode = 0 if err == 'NONET' else 1
    dialog.destroy()
    return retCode              # 0 when error is not critical or fixed (daemon has been configured)

  def start(self):    # Execute 'yandex-disk start'
    '''
    Execute 'yandex-disk start'
    and return '' if success or error message if not
    ... but sometime it starts successfully with error message '''
    try:
      msg = subprocess.check_output(['yandex-disk', 'start'], universal_newlines=True)
      debug.print('Start success, message: %s' % msg)
      return ''
    except subprocess.CalledProcessError as e:
      debug.print('Start failed:%s' % e.output)
      if e.output == '':    # probably 'os: no file'
        return 'NOTINSTALLED'
      err = ('NONET' if 'Proxy' in e.output else
             'BADDAEMON' if 'daemon' in e.output else
             'NOCONFIG')
      return err
  
  def stop(self):     # Execute 'yandex-disk stop'
    try:    msg = subprocess.check_output(['yandex-disk', 'stop'], universal_newlines=True)
    except: msg = ''
    return (msg != '')

class AppMenu(Gtk.Menu):  # Menu object
  def __init__(self):                     # Create initial menu
    global daemon
    Gtk.Menu.__init__(self)                   # Create menu
    self.status = Gtk.MenuItem();   self.status.connect("activate", self.showOutput)
    self.append(self.status)
    self.used = Gtk.MenuItem();     self.used.set_sensitive(False)
    self.append(self.used)
    self.free = Gtk.MenuItem();     self.free.set_sensitive(False)
    self.append(self.free)
    self.last = Gtk.MenuItem(_('Last synchronized items'))
    self.lastItems = Gtk.Menu()                 # Sub-menu: list of last synchronized files/folders
    self.last.set_submenu(self.lastItems)       # Add submenu (empty at the start)
    self.append(self.last)
    self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
    self.daemon_start = Gtk.MenuItem(_('Start Yandex.Disk daemon'))
    self.daemon_start.connect("activate", self.startDaemon)
    self.append(self.daemon_start)
    self.daemon_stop = Gtk.MenuItem(_('Stop Yandex.Disk daemon'))
    self.daemon_stop.connect("activate", self.stopDaemon);
    self.append(self.daemon_stop)
    open_folder = Gtk.MenuItem(_('Open Yandex.Disk Folder'))
    open_folder.connect("activate", self.openPath, daemon.yandexDiskFolder)
    self.append(open_folder)
    open_web = Gtk.MenuItem(_('Open Yandex.Disk on the web'))
    open_web.connect("activate", self.openInBrowser, 'http://disk.yandex.ru')
    self.append(open_web)
    self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
    preferences = Gtk.MenuItem(_('Preferences'))
    preferences.connect("activate", Preferences)
    self.append(preferences)
    open_help = Gtk.MenuItem(_('Help'))
    open_help.connect("activate", self.openInBrowser, 'https://yandex.ru/support/disk/')
    self.append(open_help)
    about = Gtk.MenuItem(_('About'));    about.connect("activate", self.openAbout)
    self.append(about)
    self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
    quit_app = Gtk.MenuItem(_('Quit'))
    quit_app.connect("activate", quitApplication)
    self.append(quit_app)
    self.show_all()
    self.YD_STATUS = {'idle': _('Synchronized'), 'busy': _('Sync.: '), 'none': _('Not started'),
                      'paused': _('Paused'), 'no_net': _('Not connected'), 'error':_('Error') }

  def openAbout(self, widget):            # Show About window
    widget.set_sensitive(False)         # Disable menu item
    aboutWindow = Gtk.AboutDialog()
    logo = GdkPixbuf.Pixbuf.new_from_file(logo)
    aboutWindow.set_logo(logo);   aboutWindow.set_icon(logo)
    aboutWindow.set_program_name(_('Yandex.Disk indicator'))
    aboutWindow.set_version(_('Version ') + appVer)
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

  def showOutput(self, widget):           # Display daemon output in dialogue window
    global origLANG, workLANG, deamon
    widget.set_sensitive(False)              # Disable menu item
    os.putenv('LANG', origLANG)                   # Restore user LANG appConfig
    getDaemonOutput()                             # Receve daemon output in user language
    os.putenv('LANG', workLANG)                   # Restore working LANG appConfig
    statusWindow = Gtk.Dialog(_('Yandex.Disk daemon output message'))
    statusWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
    statusWindow.set_border_width(6)
    statusWindow.add_button(_('Close'), Gtk.ResponseType.CLOSE)
    textBox = Gtk.TextView()                      # Create text-box to display daemon output
    textBox.get_buffer().set_text(daemonOutput)
    textBox.set_editable(False)
    statusWindow.get_content_area().add(textBox)  # Put it inside the dialogue content area
    statusWindow.show_all();  statusWindow.run();   statusWindow.destroy()
    widget.set_sensitive(True)               # Enable menu item

  def openInBrowser(self, widget, url):   # Open URL
    openNewBrowser(url)

  def startDaemon(self, widget):          # Start daemon
  # Try to start yandex-disk daemon and change the menu items sensitivity
    err = daemon.start()
    if err == '':
      self.updateStartStop(True)
    else:
      daemon.errorDialog(err)
      self.updateStartStop(False)

  def stopDaemon(self, widget):           # Stop daemon
    daemon.stop()
    self.updateStartStop(False)

  def openPath(self, widget, path):       # Open path
    debug.print('Opening %s' % path)
    if os.path.exists(path):
      try:    os.startfile(path)
      except: subprocess.call(['xdg-open', path])
  
  def updateInfo(self):                   # Update information in menu
    global daemon
  
    # Update status data
    self.status.set_label(_('Status: ') + self.YD_STATUS.get(daemon.status) + daemon.syncProgress)
    self.used.set_label(_('Used: ') + daemon.sUsed + '/' + daemon.sTotal)
    self.free.set_label(_('Free: ') + daemon.sFree + _(', trash: ') + daemon.sTrash)
    # --- Update last synchronized sub-menu ---
    if daemon.lastItemsChanged:                   # only when list of last synchronized is changed
      for widget in self.lastItems.get_children():  # clear last synchronized sub menu
        self.lastItems.remove(widget)
      for filePath in daemon.lastItems:
        # Make menu label as file path (shorten to 50 symbols if path length > 50 symbols),
        # with replaced underscore (to disable menu acceleration feature of GTK menu).
        widget = Gtk.MenuItem.new_with_label(
                     (filePath[: 20] + '...' + filePath[-27: ] if len(filePath) > 50 else
                      filePath).replace('_', u'\u02CD'))
        filePath = os.path.join(daemon.yandexDiskFolder, filePath)
        if os.path.exists(filePath):
          widget.set_sensitive(True)            # It can be opened
          widget.connect("activate", self.openPath, filePath)
        else:
          widget.set_sensitive(False)
        self.lastItems.append(widget)
        widget.show()
      if len(daemon.lastItems) == 0:                     # no items in list
        self.last.set_sensitive(False)
      else:                                       # there are some items in list
        self.last.set_sensitive(True)
      debug.print("Sub-menu 'Last synchronized' has been updated")
  
  def updateStartStop(self, started):     # Update daemon start and stop menu items availability
    self.daemon_start.set_sensitive(not started)
    self.daemon_stop.set_sensitive(started)
    self.status.set_sensitive(started)

class AppIcon(object):  # Indicator icon 
  def __init__(self):           # Initialize icon paths
    self.updateTheme()
    self.animationTimer = 0      # Define the icon animation timer variable

  def updateTheme(self):        # Determine paths to icons according to current theme
    global ind, installDir, appConfigPath
    # Determine theme from application configuration settings
    iconTheme = 'light' if appConfig["theme"] else 'dark'
    defaultIconThemePath = os.path.join(installDir, 'icons', iconTheme)
    userIconThemePath = os.path.join(appConfigPath, 'icons', iconTheme)
    # Set appropriate paths to icons
    userIcon = os.path.join(userIconThemePath, 'yd-ind-idle.png')
    self.idle = (userIcon if os.path.exists(userIcon) else
                 os.path.join(defaultIconThemePath, 'yd-ind-idle.png'))
    userIcon = os.path.join(userIconThemePath, 'yd-ind-pause.png')
    self.pause = (userIcon if os.path.exists(userIcon) else
                  os.path.join(defaultIconThemePath, 'yd-ind-pause.png'))
    userIcon = os.path.join(userIconThemePath, 'yd-ind-error.png')
    self.error = (userIcon if os.path.exists(userIcon) else
                  os.path.join(defaultIconThemePath, 'yd-ind-error.png'))
    userIcon = os.path.join(userIconThemePath, 'yd-busy1.png')
    if os.path.exists(userIcon):
      self.busy = userIcon
      self.themePath = userIconThemePath
    else:
      self.busy = os.path.join(defaultIconThemePath, 'yd-busy1.png')
      self.themePath = defaultIconThemePath
  
  def update(self):             # Change indicator icon according to daemon status
    global daemon, ind
  
    if daemon.status == 'busy':         # Just entered into 'busy' status
      ind.set_icon(self.busy)           # Start icon animation
      self.seqNum = 2                   # Start animation from next icon
      # Create animation timer
      self.animationTimer = GLib.timeout_add(777, self.animation, 'iconAnimation')
    else:
      if daemon.status != 'busy' and self.animationTimer > 0:  # Not 'busy' and animation is running
        stopTimer(self.animationTimer)   # Stop icon animation
        self.animationTimer = 0
      # --- Set icon for non-animated statuses ---
      if daemon.status == 'idle':
        ind.set_icon(self.idle)
      elif daemon.status == 'error':
        ind.set_icon(self.error)
      else:                             # newStatus is 'none' or 'paused'
        ind.set_icon(self.pause)
  
  def animation(self, widget):  # Changes busy icon by loop (triggered by animationTimer)
    seqFile = 'yd-busy' + str(self.seqNum) + '.png'
    ind.set_icon(os.path.join(self.themePath, seqFile))
    # calculate next icon number
    self.seqNum = self.seqNum % 5 + 1    # 5 icons in loop (1-2-3-4-5-1-2-3...)
    return True                          # True required to continue triggering by timer
  
def copyFile(source, destination):
  #debug.print("File Copy: from %s to %s" % (source, destination))
  try:    fileCopy (source, destination)
  except: debug.print("File Copy Error: from %s to %s" % (source, destination))

def deleteFile(source):
  try:    os.remove(source)
  except: debug.print('File Deletion Error: %s' % source)

def stopTimer(timerName):
  if timerName > 0:
    GLib.source_remove(timerName)

def appExit():
  lockFile.write('')
  fcntl.flock(lockFile, fcntl.LOCK_UN)
  lockFile.close()
  os._exit(0)

def quitApplication(widget):
  global iconAnimationTimer, iNotifierTimer, watchTimer, currentStatus, daemonConfigFile

  stopOnExit = appConfig.get("stoponexit", False)
  debug.print('Stop daemon on exit is - %s' % str(stopOnExit))
  if stopOnExit and currentStatus != 'none':
    stopYDdaemon()    # Stop daemon
    debug.print('Daemon is stopped')
  # --- Stop all timers ---
  stopTimer(icon.animationTimer)
  stopTimer(inotify.timer)
  stopTimer(watchTimer)
  debug.print("Timers are closed")
  appExit()

def handleEvent(triggeredBy_iNotifier):   # Perform status update
  '''
  It react (icon change/messages) on status change and also update
  status information in menu (status, sizes, last synchronized items).
  It can be called by timer (triggeredBy_iNotifier=False)
  or by iNonifier (triggeredBy_iNotifier=True)
  '''
  global daemon, watchTimer, timerTriggeredCount, menu, icon
  daemon.updateStatus()             # Get the latest status data from daemon
  debug.print(('iNonify ' if triggeredBy_iNotifier else 'Timer   ') +
              daemon.lastStatus + ' -> ' + daemon.status)
  menu.updateInfo()                  # Update information in menu
  if daemon.status != daemon.lastStatus:       # Handle status change
    icon.update()                    # Update icon
    if daemon.lastStatus == 'none':        # Daemon has been started
      menu.updateStartStop(True)         # Change menu sensitivity
      notify.send(_('Yandex.Disk'), _('Yandex.Disk daemon has been started'))
    if daemon.status == 'busy':         # Just entered into 'busy'
      notify.send(_('Yandex.Disk'), _('Synchronization started'))
    elif daemon.status == 'idle':       # Just entered into 'idle'
      if daemon.lastStatus == 'busy':      # ...from 'busy' status
        notify.send(_('Yandex.Disk'), _('Synchronization has been completed'))
    elif daemon.status =='paused':      # Just entered into 'paused'
      if daemon.lastStatus != 'none':      # ...not from 'none' status
        notify.send(_('Yandex.Disk'), _('Synchronization has been paused'))
    elif daemon.status == 'none':       # Just entered into 'none' from some another status
      menu.updateStartStop(False)        # Change menu sensitivity as daemon not started
      notify.send(_('Yandex.Disk'), _('Yandex.Disk daemon has been stopped'))
    else:                           # newStatus = 'error' or 'no-net'
      notify.send(_('Yandex.Disk'), _('Synchronization ERROR'))
  # --- Handle timer delays ---
  if triggeredBy_iNotifier:         # True means that it is called by iNonifier
    stopTimer(watchTimer)           # Recreate timer with 2 sec interval.
    watchTimer = GLib.timeout_add_seconds(2, handleEvent, False)
    timerTriggeredCount = 0         # reset counter as it was triggered not by timer
  else:
    if daemon.status != 'busy':     # in 'busy' keep update interval (2 sec.)
      if timerTriggeredCount < 9:   # increase interval up to 10 sec (2+8)
        stopTimer(watchTimer)       # Recreate watch timer.
        watchTimer = GLib.timeout_add_seconds(2 + timerTriggeredCount, handleEvent, False)
        timerTriggeredCount += 1    # Increase counter to increase delay in next activation.
  return True                       # True is required to continue activations by timer.

def activateActions():  # Install/deinstall file extensions
  activate = appConfig["fmextensions"]
  # --- Actions for Nautilus ---
  ret = subprocess.call(["dpkg -s nautilus>/dev/null 2>&1"], shell=True)
  debug.print("Nautilus installed: %s" % str(ret == 0))
  if ret == 0:
    ver = subprocess.check_output(["lsb_release -r | sed -n '1{s/[^0-9]//g;p;q}'"], shell=True)
    if ver != '' and int(ver) < 1210:
      nautilusPath = ".gnome2/nautilus-scripts/"
    else:
      nautilusPath = ".local/share/nautilus/scripts"
    debug.print(nautilusPath)
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
  debug.print("Nemo installed: %s" % str(ret == 0))
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
  debug.print("Thunar installed: %s" % str(ret == 0))
  if ret == 0:
    if activate:        # Install actions for Thunar
      if subprocess.call(["grep '" + _("Publish via Yandex.Disk") + "' " +
                          os.path.join(userHome, ".config/Thunar/uca.xml") + " >/dev/null 2>&1"],
                         shell=True) != 0:
        subprocess.call(["sed", "-i", "s/<\/actions>/<action><icon>folder-publicshare<\/icon>" +
                         '<name>"' + _("Publish via Yandex.Disk") +
                         '"<\/name><command>yandex-disk publish %f | xclip -filter -selection' +
                         ' clipboard; zenity --info ' +
                         '--window-icon=\/usr\/share\/yd-tools\/icons\/yd-128.png --title="Yandex.Disk"' +
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
                         '--window-icon=\/usr\/share\/yd-tools\/icons\/yd-128_g.png --ok-label="' +
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
  debug.print("Dolphin installed: %s" % str(ret == 0))
  if ret == 0:
    if activate:        # Install actions for Dolphin
      copyFile(os.path.join(installDir, "fm-actions/Dolphin/publish.desktop"),
               os.path.join(userHome, ".kde/share/kde4/services/publish.desktop"))
      copyFile(os.path.join(installDir, "fm-actions/Dolphin/unpublish.desktop"),
               os.path.join(userHome, ".kde/share/kde4/services/unpublish.desktop"))
    else:               # Remove actions for Dolphin
      deleteFile(os.path.join(userHome, ".kde/share/kde4/services/publish.desktop"))
      deleteFile(os.path.join(userHome," .kde/share/kde4/services/unpublish.desktop"))

###################### MAIN #########################
if __name__ == '__main__':
  ### Application constants ###
  appName = 'yandex-disk-indicator'
  appHomeName = 'yd-tools'
  installDir = os.path.join(os.sep, 'usr', 'share', appHomeName)
  userHome = os.getenv("HOME")
  logo = os.path.join(installDir, 'icons', 'yd-128.png')
  appConfigPath = os.path.join(userHome, '.config', appHomeName)
  appConfigFile = os.path.join(appConfigPath, appName + '.conf')
  # Define .desktop files locations for auto-start facility
  autoStartSource = os.path.join(os.sep, 'usr', 'share', 'applications',
                                 'Yandex.Disk-indicator.desktop')
  autoStartDestination = os.path.join(userHome, '.config', 'autostart',
                                      'Yandex.Disk-indicator.desktop')
  autoStartSource1 = os.path.join(os.sep, 'usr', 'share', 'applications', 'Yandex.Disk.desktop')
  autoStartDestination1 = os.path.join(userHome, '.config', 'autostart', 'Yandex.Disk.desktop')

  ### Output the version and environment information to debug stream
  debug = Debug(True)     # Temporary allow debug output to handle initialization messeges
  debug.print('%s v.%s (app_home=%s)' % (appName, appVer, installDir))

  ### Localization ###
  # Store original LANG environment
  origLANG = os.getenv('LANG')
  # Load translation object (or NullTranslations object when
  # translation file not found) and define _() function.
  gettext.translation(appName, '/usr/share/locale', fallback=True).install()
  # Set LANG environment for daemon output (it must be 'en' for correct parsing)
  workLANG = 'en_US.UTF-8'
  os.putenv('LANG', workLANG)

  ### Check for already running instance of the indicator application ###
  lockFileName = '/tmp/' + appName + '.lock'
  try:
    lockFile = open(lockFileName, 'w')                      # Open lock file for write
    fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)    # Try to acquire exclusive lock
  except:                                                   # File is already locked
    sys.exit(_('Yandex.Disk Indicator instance already running\n' +
               '(file /tmp/%s.lock is locked by another process)') % appName)
  lockFile.write('%d\n' % os.getpid())
  lockFile.flush()

  ### Application configuration ###
  ''' User configuration is stored in ~/.config/<appHomeName>/<appName>.conf file
      This file can contain comments (lines starts with '#') and following keywords:
        autostart, startonstart, stoponexit, notifications, theme, fmextensions, autostartdaemon
        and debug (debug is not configurable from indicator preferences dialogue)
      Dictionary appConfig stores the config settings for usage in code. Its values are saved
      to config file on Preferences dialogue exit.

      Note that daemon settings "read-only" and "overwrite" are stored
      in ~/ .config/yandex-disk/config.cfg file. They are read in checkDaemon function
      (in dictionary daemonConfig). Their values are saved to daemon config file also
      on Preferences dialogue exit.
  '''
  appConfig = Config(appConfigFile)
  # Read some settings to variables, set default values and updte some values
  appConfig['autostart'] = os.path.isfile(autoStartDestination)
  appConfig.setdefault('startonstart', True)
  appConfig.setdefault('stoponexit', False)
  # Setup on-screen notifications from config value
  notify = Notification(appName, appConfig.setdefault('notifications', True))
  appConfig.setdefault('theme', False)
  appConfig.setdefault('fmextensions', True)
  appConfig['autostartdaemon'] = os.path.isfile(autoStartDestination1)
  # initialize debug mode from config value
  debug.switch(appConfig.setdefault('debug', False))
  if not os.path.exists(appConfigPath):
    # Create app config folders in ~/.config
    try: os.makedirs(appConfigPath)
    except: pass
    # Save config with default settings
    appConfig.save()
    try: os.makedirs(os.path.join(appConfigPath, 'icons', 'light'))
    except: pass
    try: os.makedirs(os.path.join(appConfigPath, 'icons', 'dark'))
    except: pass
    # Copy icon themes description readme to user config catalogue
    copyFile(os.path.join(installDir, 'icons', 'readme'),
             os.path.join(appConfigPath, 'icons', 'readme'))
    ### Activate FM actions according to appConfig (as it is a first run)
    activateActions()
    
  ### Application Indicator ###
  ## Icons ##
  icon = AppIcon()          # Initialize icon object
  
  ### Yandex.Disk daemon object###
  daemon = YDDaemon()

  ## Indicator ##
  ind = appIndicator.Indicator.new("yandex-disk", icon.pause,
                                   appIndicator.IndicatorCategory.APPLICATION_STATUS)
  ind.set_status(appIndicator.IndicatorStatus.ACTIVE)
  menu = AppMenu()
  ind.set_menu(menu)        # Prepare and attach menu to indicator
  icon.update()             # Update indicator icon according to current status
  
  ### Create file updates watcher ###
  inotify = INotify(os.path.join(daemon.yandexDiskFolder, '.sync/cli.log'), handleEvent, True)

  ### Initial menu actualisation ###
  # Timer triggered event staff #
  watchTimer = 0            # Timer source variable
  handleEvent(True)         # update menu info and create the watch timer for 2 sec. interval
  menu.updateStartStop(daemon.status != 'none')

  ### Start GTK Main loop ###
  Gtk.main()

