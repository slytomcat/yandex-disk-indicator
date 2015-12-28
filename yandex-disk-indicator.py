#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Yandex.Disk indicator
appVer = '1.6.0'
#
#  Copyright 2014+ Sly_tom_cat <slytomcat@mail.ru>
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
import os, sys, subprocess, pyinotify, fcntl, gettext, datetime, logging

class CVal(object):
# Class to work with value that can be None, scalar value or list of values depending
# of number of elementary values added to it.

  def __init__(self, initialValue=None):
    self.val = initialValue         # store initial value
    self.index = None               # set index value (need for iter finctionality)

  def get(self):          # It just returns the current value of CVal
    return self.val

  def add(self, value):   # Add value
    if isinstance(self.val, list):  # Is it third, fourth ... value?
      self.val.append(value)        # Just append new value to list
    elif self.val == None:          # Is it first value?
      self.val = value              # Just store value
    else:                           # It is the second value.
      self.val = [self.val, value]  # Convert scalar value to list of values.
    return self.val                 # Return current value

  def __iter__(self):     # CVal iterator object initialization
    if isinstance(self.val, list):  # Is CVal a list?
      self.index = -1
    elif self.val == None:          # Is CVal not defined?
      self.index = None
    else:                           # CVal is scalar type.
      self.index = -2
    return self

  def __next__(self):     # CVal iterator support
    if self.index == None:            # Is CVal not defined or it is a second call for scalar value?
      raise StopIteration             # Stop iterations
    self.index += 1
    if self.index >= 0:               # Is CVal a list?
      if self.index < len(self.val):  # Is there a next element in list?
        return self.val[self.index]
      else:                           # There is no more elements in list.
        self.index = None             # End of list reached
        raise StopIteration           # Stop iterations
    else:                             # CVal has scalar type.
      self.index = None               # Remember that there is no more posible iterations
      return self.val

  def __str__(self):      # String representation of CVal
    return str(self.val)

class OrderedDict(ordDict):   # Redefine OrderdDict class with working setdefault

  def setdefault(self, key, val):  # Redefine not working setdefault method of OreredDict class
    try:
      return self[key]
    except:
      self[key] = val
      return val

class Config(OrderedDict):    # Configuration object

  def __init__(self, filename, load=True,
               bools=[['true', 'yes', 'y'], ['false', 'no', 'n']],
               boolval=['yes', 'no'], usequotes=True ):
    OrderedDict.__init__(self)
    self.fileName = filename
    self.bools = bools             # Values to detect booleans in self.load
    self.boolval = boolval         # Values to write booleans in self.save
    self.usequotes = usequotes     # Use qoutes for keys and values in self.save
    if load:
      self.load()

  def decode(self, value):                                # Convert string to value before store it
    #logger.debug("Decoded value: '%s'"%value)
    if value.lower() in self.bools[0]:
      value = True
    elif value.lower() in self.bools[1]:
      value = False
    return value

  def word(self, line, dc=True):                          # Get first word from beginning of line
    if line[0] == '"':                  # Is value quoted?
      end = line.find('"', 1)           # Find ending quote
      if end > 0:                       # Is ending quote exists?
        val = line[1: end]              # Divide line on word without quotes and rest of line
        rest = line[end+1: ].lstrip()   # Remove leading spaces from rest
        return (self.decode(val) if dc else val), rest  # Decode word if required
      else:                             # Error: Missed ending quote
        return None, None
    else:                               # Not quoted value.
      for i in range(len(line)):
        if line[i] in ['"', ',', ' ', '=']:   # Is it end of word?
          val = line[: i]               # Divide line on word and rest
          rest =  line[i:].lstrip()     # Remove leading spaces from rest
          if not val:                   # Is value empty?
            return None, None           # Error: Missed value
          if rest and rest[0] == '"':   # Is rest starts with '"'?
            return None, None           # Error: Missed starting quote or delimiter
          # Return word and rest line. Decode word if required.
          return (self.decode(val) if dc else val), rest
      # End of line reached: value is the whole line. Decode it if required.
      return (self.decode(line) if dc else line), ''

  def getValue(self, rest):                               # Get value(s) from string after '='
    result = CVal()                               # Result buffer
    val, rest = self.word(rest)                   # Get first value after '='
    while val != None:                            # Value was get without error
      result.add(val)                             # Store value in result
      if rest == '':
        break                                     # No more values
      elif rest[0] == ',':                        # Is next symbol ','?
        val, rest = self.word(rest[1:].lstrip())  # Get value after ','
      else:
        val = None                                # No delimiter or missed quote
    else:                                         # Some error occur while parsing after '='
      return None
    return result.get()

  def load(self, bools=[['true', 'yes', 'y'], ['false', 'no', 'n']]):
    """
    Reads config file to dictionalry (OrderedDict).
    Config file shoud conain key=value rows.
    Key can be quoted or not.
    Value can be one item or list of comma-separated items. Each value item can be quoted or not.
    When value is a single item then it creates key:value item in dictionalry
    When value is a list of items it creates key:[value, value,...] dictionary's item.
    """
    self.bools = bools
    try:
      index = 0                                           # Comment lines index
      with open(self.fileName) as cf:
        for row in cf:                                    # Parse config file lines
          row = row.strip()
          logger.debug("Line: '%s'"%row)
          if row and row[0] != '#':                       # Don't parse comments and blank lines
            key , rest = self.word(row, False)            # Get key name from beginning of line
            if key and rest[0] == '=':                    # Is it a correct key?
              rest = rest[1:].lstrip()                    # Parse rest line (after '=')
              if rest:                                    # If rest not empty
                result = self.getValue(rest)
                if result != None:                        # Is there any value in result buffer?
                  self[key] = result                      # Store it.
                else:
                  logger.error("Error in value in '%s'" % row)
              else:
                logger.error("No value specified in '%s'" % row)
            else:
              logger.error("Key error in '%s'" % row)
          else:                                           # Store comments and blank lines
            self['#'+str(index)] = row
            index += 1
            logger.debug("Comment or blank line in '%s'" % row)
      logger.info('Config read: %s' % self.fileName)
      return True
    except:
      logger.error('Config file read error: %s' % self.fileName)
      return False

  def encode(self, val):                                  # Convert value to string before save it
    if isinstance(val, bool):  # Treat Boolean
      val = self.boolval[0] if val else self.boolval[1]
    if self.usequotes:
      val = '"' + val + '"'
    return val                 # Put value within quotes

  def save(self, boolval=['yes', 'no'], usequotes=True):  # Write configuration to file
    self.usequotes = usequotes
    self.boolval = boolval
    try:
      with open(self.fileName, 'wt') as cf:
        for key, value in self.items():
          if key[0] == '#':                   # Comment or blank line
            res = value                       # Restore such lines
          else:
            if self.usequotes:
              key = '"' + key + '"'
            res = key + '='                   # Start composing config row
            for val in CVal(value):           # Iterate through the value
              res += self.encode(val) + ','   # Collect values in comma separated list
            if res[-1] == ',':
              res = res[: -1]                 # Remove last comma
          cf.write(res + '\n')                # Write resulting string in file
      logger.info('Config written: %s' % self.fileName)
      return True
    except:
      logger.error('Config file write error: %s' % self.fileName)
      return False

class Notification(object):   # On-screen notification object

  def __init__(self, app, mode):      # Initialize notification engine
    Notify.init(app)        # Initialize notification engine
    self.notifier = Notify.Notification()
    self.switch(mode)

  def switch(self, mode):             # Change show mode
    if mode:
      self.send = self.message
    else:
      self.send = lambda t, m: None

  def message(self, title, message):  # Show on-screen notification message
    global logo
    logger.debug('Message: %s | %s' % (title, message))
    self.notifier.update(title, message, logo)  # Update notification
    self.notifier.show()                        # Display new notification

class INotify(object):        # File change watcher

  def __init__(self, path, handler, par):   # Initialize watcher
    class EH(pyinotify.ProcessEvent):       # Event handler class for iNotifier
      def process_IN_MODIFY(self, event):
        handler(par)
    watchMngr = pyinotify.WatchManager()                                # Create watch manager
    self.iNotifier = pyinotify.Notifier(watchMngr, EH(), timeout=0.5)   # Create PyiNotifier
    watchMngr.add_watch(path, pyinotify.IN_MODIFY, rec = False)         # Add watch
    self.timer = Timer(700, self.handler)   # Call iNotifier handler every .7 seconds

  def handler(self):                        # iNotify working routine (called by timer)
    while self.iNotifier.check_events():
      self.iNotifier.read_events()
      self.iNotifier.process_events()
    return True

class YDDaemon(object):       # Yandex.Disk daemon interface object

  class DConfig(Config):        # Redefined class for daemon config

    def save(self):  # Update daemon config file
      # Make a copy of Self as super class
      fileConfig = Config(self.fileName, load=False)
      for key, val in self.items():
        fileConfig[key] = val
      # Convert values representations
      ro = fileConfig.pop('read-only', False)
      if ro:
        fileConfig['read-only'] = ''
      if fileConfig.pop('overwrite', False) and ro:
        fileConfig['overwrite'] = ''
      exList = fileConfig.pop('exclude-dirs', None)
      if exList != None:
        dirs = ''
        for i in CVal(exList):
          dirs += i + ','
        dirs = dirs[:-1]
        fileConfig['exclude-dirs'] = dirs
      fileConfig.save()

    def load(self):  # Get daemon config from its config file
      if super(YDDaemon.DConfig, self).load():  # Call super class method to load config from file
        # Convert values
        self['read-only'] = (self.get('read-only', False) == '')
        self['overwrite'] = (self.get('overwrite', False) == '')
        exDirs = self.get('exclude-dirs', None)
        if exDirs is None:
          self['exclude-dirs'] = None
        else:
          self['exclude-dirs'] = self.getValue(exDirs)
        return True
      else:
        return False

  def __init__(self):           # Check that daemon installed, configured and started
    if not os.path.exists('/usr/bin/yandex-disk'):
      self.ErrorDialog('NOTINSTALLED')
      appExit()                     # Daemon is not installed. Exit right now.
    self.config = self.DConfig(userHome + '/.config/yandex-disk/config.cfg',
                               load=False)
    while not self.config.load():   # Try to read Yandex.Disk configuration file
      if self.errorDialog('NOCONFIG') != 0:
        appExit()                   # User hasn't configured daemon. Exit right now.
    self.yandexDiskFolder = self.config.get('dir', '')
    while not self.getOutput():     # Check for correct daemon response and check that it is running
      try:                          # Try to find daemon running process owned by current user
        msg = subprocess.check_output(['pgrep', '-x', 'yandex-disk', '-u$USER'],
                                      universal_newlines=True)[: -1]
        logger.error('yandex-disk daemon is running but NOT responding!')
        # Kills the daemon(s) when it is running but not responding (HARON_CASE).
        try:                        # Try to kill all instances of daemon
          subprocess.check_call(['killall', 'yandex-disk'])
          logger.info('yandex-disk daemon(s) killed')
          msg = ''
        except:
          logger.error('yandex-disk daemon kill error')
          self.errorDialog('')
          appExit()                 # nonconvertible error - exit
      except:
        logger.info("yandex-disk daemon is not running")
        msg = ''
      if msg == '' and not config["startonstart"]:
        break                       # Daemon is not started and should not be started
      else:
        err = self.start()          # Try to start it
        if err != '':
          if self.errorDialog(err) != 0:
            appExit()               # Something wrong. It's no way to continue. Exit right now.
          else:
            break                   # Daemon was not started but user decided to start indicator
    else:  # while
      logger.info('yandex-disk daemon is installed, configured and responding.')
    self.status = 'none'
    self.lastStatus = 'idle'        # Fallback status for "index" status substitution at start time
    self.lastBuf = ''
    self.parseOutput()              # To update all status variables
    self.lastStatus = self.status
    self.lastBuf = '*'              # To be shure that self.lastItemsChanged = True on next time

  def getOutput(self):          # Get result of 'yandex-disk status'
    try:
      self.output = subprocess.check_output(['yandex-disk', 'status'], universal_newlines=True)
    except:
      self.output = ''      # daemon is not running or bad
    #logger.debug('output = %s' % daemonOutput)
    return self.output

  def parseOutput(self):        # Parse the daemon output
    # Look for synchronization progress
    lastPos = 0
    startPos = self.output.find('ync progress: ')
    if startPos > 0:
      startPos += 14                                # 14 is a length of 'ync progress: ' string
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
      if status == 'index':                         # Don't handle index status
        status = self.lastStatus                    # Keep last status
      if status == 'no internet access':
        status = 'no_net'
      self.status = status if status in ['busy', 'idle', 'paused', 'none', 'no_net'] else 'error'
      # Status 'error' covers 'error', 'failed to connect to daemon process' and other messages...
    else:
      self.status = 'none'
    # Look for total Yandex.Disk size
    startPos = self.output.find('Total: ', lastPos)
    if startPos > 0:
      startPos += 7                                 # 7 is len('Total: ')
      lastPos = self.output.find('\n', startPos)
      self.sTotal = self.output[startPos: lastPos]
      ## If 'Total: ' was found then other information as also should be presented
      # Look for used size                          # 6 is len('Used: ')
      startPos = self.output.find('Used: ', lastPos) + 6
      lastPos = self.output.find('\n', startPos)
      self.sUsed = self.output[startPos: lastPos]
      # Look for free size                          # 11 is len('Available: ')
      startPos = self.output.find('Available: ', lastPos) + 11
      lastPos = self.output.find('\n', startPos)
      self.sFree = self.output[startPos: lastPos]
      # Look for trash size                         # 12 is len('Trash size: ')
      startPos = self.output.find('Trash size: ', lastPos) + 12
      lastPos = self.output.find('\n', startPos)
      self.sTrash = self.output[startPos: lastPos]
    else:  # When there is no Total: then other sizes are not presented too
      self.sTotal = self.sUsed = self.sFree = self.sTrash = '...'
    # Look for last synchronized items list
    startPos = self.output.find('Last synchronized', lastPos)
    if startPos > 0:                                # skip one line
      startPos = self.output.find('\n', startPos) + 1
      buf = self.output[startPos: ]                 # save the rest
    else:
      buf = ''
    self.lastItemsChanged = (self.lastBuf != buf)   # check for changes in the list
    if self.lastItemsChanged:
      self.lastBuf = buf
      self.lastItems = []                           # clear list of file paths
      for listLine in buf.splitlines():
        startPos = listLine.find(": '")             # Find file path in the line
        if (startPos > 0):                          # File path was found
          filePath = listLine[startPos+3: -1]       # Get relative file path (skip quotes)
          self.lastItems.append(filePath)           # Store file path

  def updateStatus(self):       # Get daemon output and update all daemon YDDaemon status variables
    self.getOutput()
    self.parseOutput()

  def errorDialog(self, err):   # Show error messages according to the error
    global logo
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
      logger.debug('starting configuration utility: %s' % os.path.join(installDir, 'ya-setup'))
      retCode = subprocess.call([os.path.join(installDir,'ya-setup')])
    else:
      retCode = 0 if err == 'NONET' else 1
    dialog.destroy()
    return retCode              # 0 when error is not critical or fixed (daemon has been configured)

  def start(self):              # Execute 'yandex-disk start'
    '''
    Execute 'yandex-disk start'
    and return '' if success or error message if not
    ... but sometime it starts successfully with error message '''
    try:
      msg = subprocess.check_output(['yandex-disk', 'start'], universal_newlines=True)
      logger.info('Start success, message: %s' % msg)
      return ''
    except subprocess.CalledProcessError as e:
      logger.error('Daemon start failed:%s' % e.output)
      if e.output == '':    # probably 'os: no file'
        return 'NOTINSTALLED'
      err = ('NONET' if 'Proxy' in e.output else
             'BADDAEMON' if 'daemon' in e.output else
             'NOCONFIG')
      return err

  def stop(self):               # Execute 'yandex-disk stop'
    try:    msg = subprocess.check_output(['yandex-disk', 'stop'], universal_newlines=True)
    except: msg = ''
    return (msg != '')

class Menu(Gtk.Menu):         # Menu object

  def __init__(self):                     # Create initial menu
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
    preferences.connect("activate", self.Preferences)
    self.append(preferences)
    open_help = Gtk.MenuItem(_('Help'))
    open_help.connect("activate", self.openInBrowser, 'https://yandex.ru/support/disk/')
    self.append(open_help)
    about = Gtk.MenuItem(_('About'));    about.connect("activate", self.openAbout)
    self.append(about)
    self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
    close = Gtk.MenuItem(_('Quit'))
    close.connect("activate", self.close)
    self.append(close)
    self.show_all()
    self.YD_STATUS = {'idle': _('Synchronized'), 'busy': _('Sync.: '), 'none': _('Not started'),
                      'paused': _('Paused'), 'no_net': _('Not connected'), 'error':_('Error') }

  def openAbout(self, widget):            # Show About window
    global logo
    widget.set_sensitive(False)           # Disable menu item
    aboutWindow = Gtk.AboutDialog()
    pic = GdkPixbuf.Pixbuf.new_from_file(logo)
    aboutWindow.set_logo(pic);   aboutWindow.set_icon(pic)
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
    widget.set_sensitive(True)            # Enable menu item

  def showOutput(self, widget):           # Display daemon output in dialogue window
    global lang
    widget.set_sensitive(False)                         # Disable menu item
    statusWindow = Gtk.Dialog(_('Yandex.Disk daemon output message'))
    statusWindow.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
    statusWindow.set_border_width(6)
    statusWindow.add_button(_('Close'), Gtk.ResponseType.CLOSE)
    textBox = Gtk.TextView()                            # Create text-box to display daemon output
    lang.orig()                                         # Switch to user LANG
    textBox.get_buffer().set_text(daemon.getOutput())   # Set test to daemon output in user language
    lang.work()                                         # Restore working LANG
    textBox.set_editable(False)
    statusWindow.get_content_area().add(textBox)        # Put it inside the dialogue content area
    statusWindow.show_all();  statusWindow.run();   statusWindow.destroy()
    widget.set_sensitive(True)                          # Enable menu item

  def openInBrowser(self, widget, url):   # Open URL
    openNewBrowser(url)

  def startDaemon(self, widget):          # Start daemon
    err = daemon.start()        # Try to start yandex-disk daemon
    if err != '':
      daemon.errorDialog(err)   # Hangle the starting error
    self.updateSSS()            # Change the menu items sensitivity

  def stopDaemon(self, widget):           # Stop daemon
    daemon.stop()
    self.updateSSS()            # Change the menu items sensitivity

  def openPath(self, widget, path):       # Open path
    logger.info('Opening %s' % path)
    if os.path.exists(path):
      try:    os.startfile(path)
      except: subprocess.call(['xdg-open', path])

  class Preferences(Gtk.Dialog):          # Preferences Window

    def __init__(self, widget):                       # Show preferences window
      # Preferences Window routine
      widget.set_sensitive(False)                 # Disable menu item to avoid multiple windows creation
      # Create Preferences window
      Gtk.Dialog.__init__(self, _('Yandex.Disk-indicator and Yandex.Disk preferences'), flags=1)
      self.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
      self.set_border_width(6)
      self.add_button(_('Close'), Gtk.ResponseType.CLOSE)
      pref_notebook = Gtk.Notebook()              # Create notebook for indicator and daemon options
      self.get_content_area().add(pref_notebook)  # Put it inside the dialog content area
      # --- Indicator preferences tab ---
      preferencesBox = Gtk.VBox(spacing=5)
      key = 'autostart'                           # Auto-start indicator on system start-up
      сbAutoStart = Gtk.CheckButton(_('Start Yandex.Disk indicator when you start your computer'))
      сbAutoStart.set_active(config[key])
      сbAutoStart.connect("toggled", self.onButtonToggled, сbAutoStart, key)
      preferencesBox.add(сbAutoStart)
      key = 'startonstart'                        # Start daemon on indicator start
      сbStOnStart = Gtk.CheckButton(_('Start Yandex.Disk daemon when indicator is starting'))
      сbStOnStart.set_tooltip_text(_("When daemon was not started before."))
      сbStOnStart.set_active(config[key])
      сbStOnStart.connect("toggled", self.onButtonToggled, сbStOnStart, key)
      preferencesBox.add(сbStOnStart)
      key = 'stoponexit'                          # Stop daemon on exit
      сbStoOnExit = Gtk.CheckButton(_('Stop Yandex.Disk daemon on closing of indicator'))
      сbStoOnExit.set_active(config[key])
      сbStoOnExit.connect("toggled", self.onButtonToggled, сbStoOnExit, key)
      preferencesBox.add(сbStoOnExit)
      key = 'notifications'                       # Notifications
      сbNotify = Gtk.CheckButton(_('Show on-screen notifications'))
      сbNotify.set_active(config[key])
      сbNotify.connect("toggled", self.onButtonToggled, сbNotify, key)
      preferencesBox.add(сbNotify)
      key = 'theme'                               # Theme
      сbTheme = Gtk.CheckButton(_('Prefer light icon theme'))
      сbTheme.set_active(config[key])
      сbTheme.connect("toggled", self.onButtonToggled, сbTheme, key)
      preferencesBox.add(сbTheme)
      key = 'fmextensions'                        # Activate file-manager extensions
      сbExtensions = Gtk.CheckButton(_('Activate file manager extensions'))
      сbExtensions.set_active(config[key])
      сbExtensions.connect("toggled", self.onButtonToggled, сbExtensions, key)
      preferencesBox.add(сbExtensions)
      # --- End of Indicator preferences tab --- add it to notebook
      pref_notebook.append_page(preferencesBox, Gtk.Label(_('Indicator settings')))
      # --- Daemon start options tab ---
      optionsBox = Gtk.VBox(spacing=5)
      key = 'autostartdaemon'                     # Auto-start daemon on system start-up
      сbASDaemon = Gtk.CheckButton(_('Start Yandex.Disk daemon when you start your computer'))
      сbASDaemon.set_active(config[key])
      сbASDaemon.connect("toggled", self.onButtonToggled, сbASDaemon, key)
      optionsBox.add(сbASDaemon)
      frame = Gtk.Frame()
      frame.set_label(_("NOTE! You have to reload daemon to activate following settings"))
      frame.set_border_width(6)
      optionsBox.add(frame)
      framedBox = Gtk.VBox(homogeneous=True, spacing=5)
      frame.add(framedBox)
      key = 'read-only'                           # Option Read-Only    # daemon config
      сbRO = Gtk.CheckButton(_('Read-Only: Do not upload locally changed files to Yandex.Disk'))
      сbRO.set_tooltip_text(_("Locally changed files will be renamed if a newer version of this " +
                              "file appear in Yandex.Disk."))
      сbRO.set_active(daemon.config[key])
      сbRO.connect("toggled", self.onButtonToggled, сbRO, key)
      framedBox.add(сbRO)
      key = 'overwrite'                           # Option Overwrite    # daemon config
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
        daemon.config.save()                      # Save daemon options in config file
      if self.appCfgUpdate:
        config.save()                             # Save app config
      widget.set_sensitive(True)                  # Enable menu item
      self.destroy()

    def onButtonToggled(self, widget, button, key):   # Handle clicks on check-buttons
      toggleState = button.get_active()
      if key in ['read-only', 'overwrite']:
        daemon.config[key] = toggleState              # Update daemon config
        self.daemonCfgUpdate = True
      else:
        config[key] = toggleState                     # Update application config
        self.appCfgUpdate = True
      logger.debug('Togged: %s  val: %s' % (key, str(toggleState)))
      if key == 'theme':
        icon.updateTheme()                            # Update themeStyle
        icon.update()                                 # Update current icon
      elif key == 'notifications':
        notify.switch(toggleState)                    # Update notification object
      elif key == 'autostartdaemon':
        if toggleState:
          copyFile(autoStartDaemonSrc, autoStartDaemonDst)
          notify.send(_('Yandex.Disk daemon'), _('Auto-start ON'))
        else:
          deleteFile(autoStartDaemonDst)
          notify.send(_('Yandex.Disk daemon'), _('Auto-start OFF'))
      elif key == 'autostart':
        if toggleState:
          copyFile(autoStartIndSrc, autoStartIndDst)
          notify.send(_('Yandex.Disk Indicator'), _('Auto-start ON'))
        else:
          deleteFile(autoStartIndDst)
          notify.send(_('Yandex.Disk Indicator'), _('Auto-start OFF'))
      elif key == 'fmextensions':
        activateActions()
      elif key == 'read-only':
        self.overwrite.set_sensitive(toggleState)

    class excludeDirsList(Gtk.Dialog):                # Excluded list dialogue

      def __init__(self, widget, parent):   # show current list
        self.parent = parent
        self.changed = False
        Gtk.Dialog.__init__(self, title=_('Folders that are excluded from synchronization'),
                            parent=parent, flags=1)
        self.set_icon(GdkPixbuf.Pixbuf.new_from_file(logo))
        self.set_border_width(6)
        self.add_button(_('Add catalogue'),
                        Gtk.ResponseType.APPLY).connect("clicked", self.addFolder, self)
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

      def exitFromDialog(self, widget):     # Save list from dialogue to "exclude-dirs" property
        if self.changed:
          exList = CVal()                                     # Store path value from dialogue rows
          listIter = self.excludeList.get_iter_first()
          while listIter != None:
            exList.add(self.excludeList.get(listIter, 1)[0])
            listIter = self.excludeList.iter_next(listIter)
          daemon.config['exclude-dirs'] = exList.get()        # Save collected value
          self.parent.daemonCfgUpdate = True                  # Inform parent about changed list
        self.destroy()                                        # Close dialogue

      def lineToggled(self, widget, path):  # Line click handler, it switch row selection
        self.excludeList[path][0] = not self.excludeList[path][0]

      def deleteSelected(self, widget):     # Remove selected rows from list
        listIiter = self.excludeList.get_iter_first()
        while listIiter != None and self.excludeList.iter_is_valid(listIiter):
          if self.excludeList.get(listIiter, 0)[0]:
            self.excludeList.remove(listIiter)
            self.changed = True
          else:
            listIiter = self.excludeList.iter_next(listIiter)

      def addFolder(self, widget, parent):  # Add new path to list via FileChooserDialog
        dialog = Gtk.FileChooserDialog(_('Select catalogue to add to list'), parent,
                                     Gtk.FileChooserAction.SELECT_FOLDER,
                                     (_('Close'), Gtk.ResponseType.CANCEL,
                                      _('Select'), Gtk.ResponseType.ACCEPT))
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.set_current_folder(daemon.yandexDiskFolder)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
          res = os.path.relpath(dialog.get_filename(), start=daemon.yandexDiskFolder)
          self.excludeList.append([False, res])
          self.changed = True
        dialog.destroy()

  def update(self):                       # Update information in menu
    # Update status data
    self.status.set_label(_('Status: ') + self.YD_STATUS.get(daemon.status) +
                          (daemon.syncProgress if daemon.status == 'busy' else ''))
    self.used.set_label(_('Used: ') + daemon.sUsed + '/' + daemon.sTotal)
    self.free.set_label(_('Free: ') + daemon.sFree + _(', trash: ') + daemon.sTrash)
    # --- Update last synchronized sub-menu ---
    if daemon.lastItemsChanged:                     # Only when list of last synchronized is changed
      for widget in self.lastItems.get_children():  # Clear last synchronized sub-menu
        self.lastItems.remove(widget)
      for filePath in daemon.lastItems:             # Create new sub-menu items
        # Make menu label as file path (shorten to 50 symbols if path length > 50 symbols),
        # with replaced underscore (to disable menu acceleration feature of GTK menu).
        widget = Gtk.MenuItem.new_with_label(
                     (filePath[: 20] + '...' + filePath[-27: ] if len(filePath) > 50 else
                      filePath).replace('_', u'\u02CD'))
        # Make full path
        filePath = os.path.join(daemon.yandexDiskFolder, filePath)
        if os.path.exists(filePath):
          widget.set_sensitive(True)                # If it exists then it can be opened
          widget.connect("activate", self.openPath, filePath)
        else:
          widget.set_sensitive(False)               # Don't allow to open nonexisting path
        self.lastItems.append(widget)
        widget.show()
      if len(daemon.lastItems) == 0:                # No items in list?
        self.last.set_sensitive(False)
      else:                                         # There are some items in list
        self.last.set_sensitive(True)
      logger.info("Sub-menu 'Last synchronized' has been updated")

  def updateSSS(self):                    # Update daemon start, stop & status menu availability
    started = daemon.status != 'none'
    self.daemon_stop.set_sensitive(started)
    self.status.set_sensitive(started)
    self.daemon_start.set_sensitive(not started)

  def close(self, widget):                # Quit from indicator
    global wTimer
    stopOnExit = config.get("stoponexit", False)
    logger.info('Stop daemon on exit - %s' % str(stopOnExit))
    if stopOnExit and daemon.status != 'none':
      daemon.stop()   # Stop daemon
      logger.info('Daemon is stopped')
    # --- Stop all timers ---
    icon.timer.stop()
    inotify.timer.stop()
    wTimer.stop()
    logger.info("Timers are stopped")
    appExit()

class Icon(object):           # Indicator icon

  def __init__(self):     # Initialize icon paths
    self.updateTheme()
    # Create timer object for the icon animation
    self.timer = Timer(777, self.animation, start=False)

  def updateTheme(self):  # Determine paths to icons according to current theme
    global installDir, configPath
    # Determine theme from application configuration settings
    iconTheme = 'light' if config["theme"] else 'dark'
    defaultIconThemePath = os.path.join(installDir, 'icons', iconTheme)
    userIconThemePath = os.path.join(configPath, 'icons', iconTheme)
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

  def update(self):       # Change indicator icon according to daemon status
    global ind
    if daemon.status == 'busy':         # Just entered into 'busy' status
      ind.set_icon(self.busy)           # Start animation from first busy icon
      self.seqNum = 2                   # Next icon for animation
      self.timer.start()                # Start animation timer
    else:
      if daemon.status != 'busy' and self.timer.active:  # Not 'busy' and animation is on
        self.timer.stop()               # Stop icon animation
      # --- Set icon for non-animated statuses ---
      if daemon.status == 'idle':
        ind.set_icon(self.idle)
      elif daemon.status == 'error':
        ind.set_icon(self.error)
      else:                             # status is 'none' or 'paused'
        ind.set_icon(self.pause)

  def animation(self):    # Changes busy icon by loop (triggered by self.timer)
    seqFile = 'yd-busy' + str(self.seqNum) + '.png'
    ind.set_icon(os.path.join(self.themePath, seqFile))
    # calculate next icon number
    self.seqNum = self.seqNum % 5 + 1    # 5 icons in loop (1-2-3-4-5-1-2-3...)
    return True                          # True required to continue triggering by timer

class LockFile(object):       # LockFile object

  def __init__(self, fileName):
    ### Check for already running instance of the indicator application in user space ###
    self.fileName = fileName
    logger.debug('Lock file is:%s' % self.fileName)
    try:                                                          # Open lock file for write
      self.lockFile = (open(self.fileName, 'r+') if os.path.exists(self.fileName) else
                       open(self.fileName, 'w'))
      fcntl.flock(self.lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)   # Try to acquire exclusive lock
      logger.debug('Lock file succesfully locked.')
    except:                                                       # File is already locked
      sys.exit(_('%s instance is already running\n' +
                 '(file %s is locked by another process)') % (appName, self.fileName))
    self.lockFile.write('%d\n' % os.getpid())
    self.lockFile.flush()

  def release(self):
    fcntl.flock(self.lockFile, fcntl.LOCK_UN)
    self.lockFile.close()

class Timer(object):          # Timer object

  def __init__(self, interval, handler, par = None, start = True):
    self.interval = interval          # Timer interval (ms)
    self.handler = handler            # Handler function
    self.par = par                    # Parameter of handler function
    self.active = False               # Current activity status
    if start:
      self.start()                    # Start timer if requered

  def start(self, interval = None):   # Start inactive timer or update if it is active
    if interval is None:
      interval = self.interval
    if not self.active:
      if self.par is None:
        self.timer = GLib.timeout_add(interval, self.handler)
      else:
        self.timer = GLib.timeout_add(interval, self.handler, self.par)
      self.active = True
      logger.debug('timer started %s %s' %(self.timer, interval))
    else:
      self.update(interval)

  def update(self, interval):         # Update interval (restart active, not start if inactive)
    if interval != self.interval:
      self.interval = interval
      if self.active:
        self.stop()
        self.start()

  def stop(self):                     # Stop active timer
    if self.active:
      logger.debug('timer to stop %s %s' %(self.timer, self.interval))
      GLib.source_remove(self.timer)
      self.active = False

class Language(object):       # Language object

  def __init__(self):
    self.origLANG = os.getenv('LANG')    # Store original LANG environment
    self.workLANG = 'en_US.UTF-8'
    # Load translation object (or NullTranslations object when
    # translation file not found) and define _() function.
    gettext.translation(appName, '/usr/share/locale', fallback=True).install()
    # Set LANG environment for daemon output (it must be 'en' for correct parsing)
    self.work()
    logger.info('User LANG is '+self.origLANG)

  def orig(self):  # Set original user language
    os.putenv('LANG', self.origLANG)

  def work(self):  # Set working language for daemon output correct parsing
    os.putenv('LANG', self.workLANG)

def copyFile(source, destination):
  try:    fileCopy (source, destination)
  except: logger.error("File Copy Error: from %s to %s" % (source, destination))

def deleteFile(source):
  try:    os.remove(source)
  except: logger.error('File Deletion Error: %s' % source)

def appExit():
  flock.release()
  os._exit(0)

def handleEvent(byNotifier):  # Perform status update
  '''
  It handles daemon status changes by updating icon, creting messages and also update
  status information in menu (status, sizes and list of last synchronized items).
  It can be called by timer (when byNotifier=False) or by iNonifier
  (when byNotifier=True)
  '''
  global tCnt, wTimer
  daemon.updateStatus()                   # Get the latest status data from daemon
  logger.info(('iNonify ' if byNotifier else 'Timer   ') +
              daemon.lastStatus + ' -> ' + daemon.status)
  menu.update()                           # Update information in menu
  if daemon.status != daemon.lastStatus:  # Handle status change
    icon.update()                         # Update icon
    if daemon.lastStatus == 'none':       # Daemon has been started
      menu.updateSSS()                    # Change menu sensitivity
      notify.send(_('Yandex.Disk'), _('Yandex.Disk daemon has been started'))
    if daemon.status == 'busy':           # Just entered into 'busy'
      notify.send(_('Yandex.Disk'), _('Synchronization started'))
    elif daemon.status == 'idle':         # Just entered into 'idle'
      if daemon.lastStatus == 'busy':     # ...from 'busy' status
        notify.send(_('Yandex.Disk'), _('Synchronization has been completed'))
    elif daemon.status =='paused':        # Just entered into 'paused'
      if daemon.lastStatus != 'none':     # ...not from 'none' status
        notify.send(_('Yandex.Disk'), _('Synchronization has been paused'))
    elif daemon.status == 'none':         # Just entered into 'none' from some another status
      menu.updateSSS()                    # Change menu sensitivity as daemon not started
      notify.send(_('Yandex.Disk'), _('Yandex.Disk daemon has been stopped'))
    else:                                 # newStatus = 'error' or 'no-net'
      notify.send(_('Yandex.Disk'), _('Synchronization ERROR'))
  # --- Handle timer delays ---
  if byNotifier:                          # True means that it is called by iNonifier
    wTimer.update(2000)                   # Set timer interval to 2 sec.
    tCnt = 0                              # reset counter as it was triggered not by timer
  else:                                   # It called by timer
    if daemon.status != 'busy':           # in 'busy' keep update interval (2 sec.)
      if tCnt < 9:                        # increase interval up to 10 sec (2 + 8)
        wTimer.update((2 + tCnt)*1000)    # Update timer interval.
        tCnt += 1                         # Increase counter to increase delay in next activation.
  return True                             # True is required to continue activations by timer.

def activateActions():        # Install/deinstall file extensions
  activate = config["fmextensions"]
  # --- Actions for Nautilus ---
  ret = subprocess.call(["dpkg -s nautilus>/dev/null 2>&1"], shell=True)
  logger.info("Nautilus installed: %s" % str(ret == 0))
  if ret == 0:
    ver = subprocess.check_output(["lsb_release -r | sed -n '1{s/[^0-9]//g;p;q}'"], shell=True)
    if ver != '' and int(ver) < 1210:
      nautilusPath = ".gnome2/nautilus-scripts/"
    else:
      nautilusPath = ".local/share/nautilus/scripts"
    logger.debug(nautilusPath)
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
  logger.info("Nemo installed: %s" % str(ret == 0))
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
  logger.info("Thunar installed: %s" % str(ret == 0))
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
  logger.info("Dolphin installed: %s" % str(ret == 0))
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
  configPath = os.path.join(userHome, '.config', appHomeName)
  # Define .desktop files locations for auto-start facility
  autoStartIndSrc = os.path.join(os.sep, 'usr', 'share', 'applications',
                                 'Yandex.Disk-indicator.desktop')
  autoStartIndDst = os.path.join(userHome, '.config', 'autostart', 'Yandex.Disk-indicator.desktop')
  autoStartDaemonSrc = os.path.join(os.sep, 'usr', 'share', 'applications', 'Yandex.Disk.desktop')
  autoStartDaemonDst = os.path.join(userHome, '.config', 'autostart', 'Yandex.Disk.desktop')

  ### Output the version and environment information to console output
  print('%s v.%s' % (appName, appVer))

  ### Logging ###
  '''
  Logging level can be set via command line parameter:
    -l<n>     where n is one of the logging levels: 10, 20, 30, 40 or 50 (see below)
  Logging level can be:
    10 - to show all messages (DEBUG)
    20 - to show all messages except debugging messages (INFO)
    30 - to show all messages except debugging and info messages (WARNING)
    40 - to show all messages except debugging, info and warning messages (ERROR)
    50 - to show critical messages only (CRITICAL) '''

  logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s')
  logger = logging.getLogger('')
  # Check command line arguments for logging level options
  logger.setLevel(30)
  for opt in sys.argv[1:]:
    if opt[:2] == '-l':
      logger.setLevel(int(opt[2:]))

  logger.info('Logging level: '+str(logger.getEffectiveLevel()))

  ### Localization ###
  lang = Language()

  ### Application configuration ###
  '''
  User configuration is stored in ~/.config/<appHomeName>/<appName>.conf file.
  This file can contain comments (line starts with '#') and config values in
  form: key=value[,value[,value ...]] where keys and values can be quoted ("...") or not.
  The following key words are reserved for configuration:
    autostart, startonstart, stoponexit, notifications, theme, fmextensions and autostartdaemon.

  The dictionary 'config' stores the config settings for usage in code. Its values are saved to
  config file on the Menu.Preferences dialogue exit or on application start when cofig
  file is not exists.

  Note that daemon settings ("read-only", "overwrite" and "exclude_dir") are stored
  in ~/ .config/yandex-disk/config.cfg file. They are read in YDDaemon.__init__() method
  (in dictionary YDDaemon.config). Their values are saved to daemon config file also
  on Menu.Preferences dialogue exit.
  '''
  config = Config(os.path.join(configPath, appName + '.conf'))
  # Read some settings to variables, set default values and update some values
  config['autostart'] = os.path.isfile(autoStartIndDst)
  config.setdefault('startonstart', True)
  config.setdefault('stoponexit', False)
  # Setup on-screen notification settings from config value
  notify = Notification(appName, config.setdefault('notifications', True))
  config.setdefault('theme', False)
  config.setdefault('fmextensions', True)
  config['autostartdaemon'] = os.path.isfile(autoStartDaemonDst)
  if not os.path.exists(configPath):   # Is i first run?
    print('Info: No config, probably it is a first run.')
    # Create app config folders in ~/.config
    try: os.makedirs(configPath)
    except: pass
    # Save config with default settings
    config.save()
    try: os.makedirs(os.path.join(configPath, 'icons', 'light'))
    except: pass
    try: os.makedirs(os.path.join(configPath, 'icons', 'dark'))
    except: pass
    # Copy icon themes description readme to user config catalogue
    copyFile(os.path.join(installDir, 'icons', 'readme'),
             os.path.join(configPath, 'icons', 'readme'))
    ### Activate FM actions according to config (as it is a first run)
    activateActions()

  ### Check for already running instance of the indicator application in user space ###
  flock = LockFile(os.path.join(configPath, 'pid'))

  ### Application Indicator ###
  ## Icons ##
  icon = Icon()             # Initialize icon object

  ### Yandex.Disk daemon connection object ###
  daemon = YDDaemon()       # Initialize daemon connector

  ## Indicator ##
  ind = appIndicator.Indicator.new("yandex-disk", icon.pause,
                                   appIndicator.IndicatorCategory.APPLICATION_STATUS)
  ind.set_status(appIndicator.IndicatorStatus.ACTIVE)
  menu = Menu()
  ind.set_menu(menu)        # Prepare and attach menu to indicator
  icon.update()             # Update indicator icon according to current daemon status

  ### Create file updates watcher ###
  inotify = INotify(os.path.join(daemon.yandexDiskFolder, '.sync/cli.log'), handleEvent, True)

  ### Initial menu actualisation ###
  # Timer triggered event staff #
  wTimer = Timer(2000, handleEvent, False)    # Timer object
  handleEvent(True)                           # Update menu info on initialization
  menu.updateSSS()

  ### Start GTK Main loop ###
  Gtk.main()

