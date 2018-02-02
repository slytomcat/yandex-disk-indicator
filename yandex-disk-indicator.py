#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
appName = 'yandex-disk-indicator'
appVer = '1.9.18'
#
from datetime import datetime
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

from os import remove, makedirs, getpid, geteuid, getenv
from pyinotify import ProcessEvent, WatchManager, Notifier, IN_MODIFY, IN_ACCESS
from gi import require_version
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('AppIndicator3', '0.1')
from gi.repository import AppIndicator3 as appIndicator
require_version('Notify', '0.7')
from gi.repository import Notify
require_version('GLib', '2.0')
from gi.repository.GLib import timeout_add, source_remove
require_version('GdkPixbuf', '2.0')
from gi.repository.GdkPixbuf import Pixbuf
from subprocess import check_output, call, CalledProcessError
from re import findall as reFindall, sub as reSub, search as reSearch, M as reM, S as reS
from argparse import ArgumentParser
from gettext import translation
from logging import basicConfig, getLogger
from os.path import exists as pathExists, join as pathJoin, relpath as relativePath, expanduser
from shutil import copy as fileCopy, which
from datetime import datetime
from webbrowser import open_new as openNewBrowser
from signal import signal, SIGTERM
from sys import exit as sysExit

#################### Common utility functions and classes ####################
def copyFile(src, dst):
  try:
    fileCopy(src, dst)
  except:
    logger.error("File Copy Error: from %s to %s" % (src, dst))

def deleteFile(dst):
  try:
    remove(dst)
  except:
    logger.error('File Deletion Error: %s' % dst)

def makeDirs(dst):
  try:
    makedirs(dst, exist_ok=True)
  except:
    logger.error('Dirs creation Error: %s' % dst)

def shortPath(path):
  return (path[: 20] + '...' + path[-27:] if len(path) > 50 else path).replace('_', '\u02CD')

class CVal(object):             # Multivalue helper
  ''' Class to work with value that can be None, scalar item or list of items depending
      of number of elementary items added to it or it contain. '''

  def __init__(self, initialValue=None):
    self.set(initialValue)   # store initial value
    self.index = None

  def get(self):                  # It just returns the current value of cVal
    return self.val

  def set(self, value):           # Set internal value
    self.val = value
    if isinstance(self.val, list) and len(self.val) == 1:
      self.val = self.val[0]
    return self.val

  def add(self, item):            # Add item
    if isinstance(self.val, list):  # Is it third, fourth ... value?
      self.val.append(item)         # Just append new item to list
    elif self.val is None:          # Is it first item?
      self.val = item               # Just store item
    else:                           # It is the second item.
      self.val = [self.val, item]   # Convert scalar value to list of items.
    return self.val

  def __iter__(self):             # cVal iterator object initialization
    if isinstance(self.val, list):  # Is CVal a list?
      self.index = -1
    elif self.val is None:          # Is CVal not defined?
      self.index = None
    else:                           # CVal is scalar type.
      self.index = -2
    return self

  def __next__(self):             # cVal iterator support
    if self.index is None:            # Is CVal not defined?
      raise StopIteration             # Stop iterations
    self.index += 1
    if self.index >= 0:               # Is CVal a list?
      if self.index < len(self.val):  # Is there a next element in list?
        return self.val[self.index]
      else:                           # There is no more elements in list.
        self.index = None
        raise StopIteration           # Stop iterations
    else:                             # CVal has scalar type.
      self.index = None               # Remember that there is no more iterations possible
      return self.val

  def __bool__(self):
    return self.val is not None

class Config(dict):             # Configuration

  def __init__(self, fileName, load=True,
               bools=[['true', 'yes', 'y'], ['false', 'no', 'n']],
               boolval=['yes', 'no'], usequotes=True, delimiter='='):
    super().__init__()
    self.fileName = fileName
    self.bools = bools             # Values to detect boolean in self.load
    self.boolval = boolval         # Values to write boolean in self.save
    self.usequotes = usequotes     # Use quotes for keys and values in self.save
    self.delimiter = delimiter     # Use specified delimiter between key and value
    self.changed = False           # Change flag (for use outside of the class)
    if load:
      self.load()

  def decode(self, value):              # Convert string to value before store it
    if value.lower() in self.bools[0]:
      value = True
    elif value.lower() in self.bools[1]:
      value = False
    return value

  def getValue(self, st):               # Find value(s) in string after '='
    v = CVal()                                    # Value accumulator
    st = st.strip()                               # Remove starting and ending spaces
    if st.startswith(','):
      return None                                 # Error: String after '=' starts with comma
    while True:
      s = reSearch(r'^("[^"]*")|^([^",#]+)', st)  # Search for quoted or value without quotes
      if s is None:
        return None                               # Error: Nothing found but value expected
      start, end = s.span()
      vv = st[start: end].strip()                 # Get found value
      if vv.startswith('"'):
        vv = vv[1: -1]                            # Remove quotes
      v.add(self.decode(vv))                      # Decode and store value
      st = st[end:].lstrip()                      # Remove value and following spaces from string
      if st == '':
        return v.get()                            # EOF normaly reached (after last value in string)
      else:                                       # String still contain something
        if st.startswith(','):                    # String is continued with comma?
          st = st[1:].lstrip()                    # Remove comma and following spaces
          if st != '':                            # String is continued after comma?
            continue                              # Continue to search values
          # else:                                 # Error: No value after comma
        # else:                                   # Error: Next symbol is not comma
        return None                               # Error

  def load(self, bools=[['true', 'yes', 'y'], ['false', 'no', 'n']], delimiter='='):
    """
    Reads config file to dictionary.
    Config file should contain key=value rows.
    Key can be quoted or not.
    Value can be one item or list of comma-separated items. Each value item can be quoted or not.
    When value is a single item then it creates key:value item in dictionary
    When value is a list of items it creates key:[value, value,...] dictionary's item.
    """
    self.bools = bools
    self.delimiter = delimiter
    try:                              # Read configuration file into list of tuples ignoring blank
                                      # lines, lines without delimiter, and lines with comments.
      with open(self.fileName) as cf:
        res = [reFindall(r'^\s*(.+?)\s*%s\s*(.*)$' % self.delimiter, l)[0]
               for l in cf if l and self.delimiter in l and l.lstrip()[0] != '#']
      self.readSuccess = True
    except:
      logger.error('Config file read error: %s' % self.fileName)
      self.readSuccess = False
      return False
    for kv, vv in res:                # Parse each line
      # Check key
      key = reFindall(r'^"([^"]+)"$|^([\w-]+)$', kv)
      if key == []:
        logger.warning('Wrong key in line \'%s %s %s\'' % (kv, self.delimiter, vv))
      else:                           # Key is OK
        key = key[0][0] + key[0][1]   # Join two possible keys variants (with and without quotes)
        if vv.strip() == '':
          logger.warning('No value specified in line \'%s %s %s\'' % (kv, self.delimiter, vv))
        else:                         # Value is not empty
          value = self.getValue(vv)   # Parse values
          if value is None:
            logger.warning('Wrong value(s) in line \'%s %s %s\'' % (kv, self.delimiter, vv))
          else:                       # Value is OK
            if key in self.keys():    # Check double values
              logger.warning(('Double values for one key:\n%s = %s\nand\n%s = %s\n' +
                              'Last one is stored.') % (key, self[key], key, value))
            self[key] = value         # Store last value
            logger.debug('Config value read as: %s = %s' % (key, str(value)))
    logger.info('Config read: %s' % self.fileName)
    return True

  def encode(self, val):                # Convert value to string before save it
    if isinstance(val, bool):       # Treat Boolean
      val = self.boolval[0] if val else self.boolval[1]
    if self.usequotes:
      val = '"' + val + '"'         # Put value within quotes
    return val

  def save(self, boolval=['yes', 'no'], usequotes=True, delimiter='='):
    self.usequotes = usequotes
    self.boolval = boolval
    self.delimiter = delimiter
    try:                                  # Read the file in buffer
      with open(self.fileName, 'rt') as cf:
        buf = cf.read()
    except:
      logger.warning('Config file access error, a new file (%s) will be created' % self.fileName)
      buf = ''
    buf = reSub(r'[\n]*$', '\n', buf)     # Remove all ending blank lines except the one.
    for key, value in self.items():
      if value is None:
        res = ''                          # Remove 'key=value' from file if value is None
        logger.debug('Config value \'%s\' will be removed' % key)
      else:                               # Make a line with value
        res = self.delimiter.join([key,
                                   ', '.join([self.encode(val) for val in CVal(value)])]) + '\n'
        logger.debug('Config value to save: %s' % res[:-1])
      # Find line with key in file the buffer
      sRe = reSearch(r'^[ \t]*["]?%s["]?[ \t]*%s.+\n' % (key, self.delimiter), buf, flags=reM)
      if sRe is not None:                 # Value has been found
        buf = sRe.re.sub(res, buf)        # Replace it with new value
      elif res != '':                     # Value was not found and value is not empty
        buf += res                        # Add new value to end of file buffer
    try:
      with open(self.fileName, 'wt') as cf:
        cf.write(buf)                     # Write updated buffer to file
    except:
      logger.error('Config file write error: %s' % self.fileName)
      return False
    logger.info('Config written: %s' % self.fileName)
    self.changed = False                  # Reset flag of change in not stored config
    return True

class Timer(object):            # Timer for triggering a function periodically
  ''' Timer class methods:
        __init__ - initialize the timer object with specified interval and handler. Start it
                   if start value is not False. par - is parameter for handler call.
        start    - Start timer. Optionally the new interval can be specified and if timer is
                   already running then the interval is updated (timer restarted with new interval).
        update   - Updates interval. If timer is running it is restarted with new interval. If it
                   is not running - then new interval is just stored.
        stop     - Stop running timer or do nothing if it is not running.
      Interface variables:
        active   - True when timer is currently running, otherwise - False
  '''
  def __init__(self, interval, handler, par=None, start=True):
    self.interval = interval          # Timer interval (ms)
    self.handler = handler            # Handler function
    self.par = par                    # Parameter of handler function
    self.active = False               # Current activity status
    if start:
      self.start()                    # Start timer if required

  def start(self, interval=None):   # Start inactive timer or update if it is active
    if interval is None:
      interval = self.interval
    if not self.active:
      self.interval = interval
      if self.par is None:
        self.timer = timeout_add(interval, self.handler)
      else:
        self.timer = timeout_add(interval, self.handler, self.par)
      self.active = True
      # logger.debug('timer started %s %s' %(self.timer, interval))
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
      # logger.debug('timer to stop %s' %(self.timer))
      source_remove(self.timer)
      self.active = False

class Notification(object):     # On-screen notification

  def __init__(self, title):    # Initialize notification engine
    if not Notify.is_initted():
      Notify.init(appName)
    self.title = title
    self.note = None

  def send(self, messg):
    global logo
    logger.debug('Message: %s | %s' % (self.title, messg))
    if self.note is not None:
      try:
        self.note.close()
      except:
        pass
      self.note = None
    try:                            # Create notification
      self.note = Notify.Notification.new(self.title, messg)
      self.note.set_image_from_pixbuf(logo)
      self.note.show()              # Display new notification
    except:
      logger.error('Message engine failure')

#################### Main daemon/indicator classes ####################
class YDDaemon(object):         # Yandex.Disk daemon interface
  '''
  This is the fully automated class that serves as daemon interface.
  Public methods:
  __init__ - Handles initialization of the object and as a part - auto-start daemon if it
             is required by configuration settings.
  getOuput - Provides daemon output (in user language when optional parameter userLang is
             True)
  start    - Request to start daemon. Do nothing if it is alreday started
  stop     - Request to stop daemon. Do nothing if it is not started
  exit     - Handles 'Stop on exit' facility according to daemon configuration settings.
  change   - Call-back function for handling daemon status changes outside the class.
             It have to be redefined by UI class.
             The parameters of the call - status values dictionary (see vars description below)

  Class interface variables:
  config   - The daemon configuration dictionary (object of _DConfig(Config) class)
  vars     - status values dictionary with following keys:
              'status' - current daemon status
              'progress' - synchronization progress or ''
              'laststatus' - previous daemon status
              'statchg' - True indicates that status was changed
              'total' - total Yandex disk space
              'used' - currently used space
              'free' - available space
              'trash' - size of trash
              'szchg' - True indicates that sizes were changed
              'lastitems' - list of last synchronized items or []
              'lastchg' - True indicates that lastitems was changed
              'error' - error message
              'path' - path of error
  ID       - the daemon identity string (empty in single daemon configuration)
  '''

  class _Watcher(object):               # Daemon iNotify watcher
    '''
    iNotify watcher object for monitor of changes daemon internal log for the fastest
    reaction on status change.
    '''
    def __init__(self, path, handler, par=None):
      # Watched path
      self.path = pathJoin(path.replace('~', userHome), '.sync/cli.log')
      # Initialize iNotify watcher
      class _EH(ProcessEvent):           # Event handler class for iNotifier
        def process_IN_MODIFY(self, event):
          handler(par)
      self._watchMngr = WatchManager()   # Create watch manager
      # Create PyiNotifier
      self._iNotifier = Notifier(self._watchMngr, _EH(), timeout=0.5)
      # Timer will call iNotifier handler
      def iNhandle():                    # iNotify working routine (called by timer)
        while self._iNotifier.check_events():
          self._iNotifier.read_events()
          self._iNotifier.process_events()
        return True
      self._timer = Timer(700, iNhandle, start=False)  # not started initially
      self._status = False

    def start(self):               # Activate iNotify watching
      if self._status:
        return
      if not pathExists(self.path):
        logger.info("iNotiy was not started: path '"+self.path+"' was not found.")
        return
      self._watch = self._watchMngr.add_watch(self.path, IN_MODIFY|IN_ACCESS, rec=False)
      self._timer.start()
      self._status = True

    def stop(self):                      # Stop iNotify watching
      if not self._status:
        return
      # Remove watch
      self._watchMngr.rm_watch(self._watch[self.path])
      # Stop timer
      self._timer.stop()
      self._status = False

  class _DConfig(Config):               # Redefined class for daemon config

    def save(self):  # Update daemon config file
      # Make a new Config object
      fileConfig = Config(self.fileName, load=False)
      # Copy values that could be changed to the new Config object and convert representation
      ro = self.get('read-only', False)
      fileConfig['read-only'] = '' if ro else None
      fileConfig['overwrite'] = '' if self.get('overwrite', False) and ro else None
      fileConfig['startonstartofindicator'] = self.get('startonstartofindicator', True)
      fileConfig['stoponexitfromindicator'] = self.get('stoponexitfromindicator', False)
      exList = self.get('exclude-dirs', None)
      fileConfig['exclude-dirs'] = (None if exList is None else
                                    ', '.join([v  for v in CVal(exList)]))
      # Store changed values
      fileConfig.save()
      self.changed = False

    def load(self):  # Get daemon config from its config file
      if super().load():                                    # Load config from file
        # Convert values representations
        self['read-only'] = (self.get('read-only', None) == '')
        self['overwrite'] = (self.get('overwrite', None) == '')
        self.setdefault('startonstartofindicator', True)    # New value to start daemon individually
        self.setdefault('stoponexitfromindicator', False)   # New value to stop daemon individually
        exDirs = self.setdefault('exclude-dirs', None)
        if exDirs is not None and not isinstance(exDirs, list):
          # Additional parsing required when quoted value like "dir,dir,dir" is specified.
          # When the value specified without quotes it will be already list value [dir, dir, dir].
          self['exclude-dirs'] = self.getValue(exDirs)
        return True
      else:
        return False

  def __init__(self, cfgFile, ID):      # Check that daemon installed and configured
    '''
    cfgFile  - full path to config file
    ID       - identity string '#<n> ' in multi-instance environment or
               '' in single instance environment'''
    self.ID = ID                                      # Remember daemon identity
    self.YDC = which('yandex-disk')
    if not self.YDC:
      self._errorDialog('NOTINSTALLED')
      appExit('Daemon is not installed')
    # Try to read Yandex.Disk configuration file and make sure that it is correctly configured
    self.config = self._DConfig(cfgFile, load=False)
    while not (self.config.load() and
               pathExists(self.config.get('dir', '')) and
               pathExists(self.config.get('auth', ''))):
      if self._errorDialog('NOCONFIG') != 0:
        if ID != '':
          self.config['dir'] = ''
          # Exit from loop in multi-instance configuration
          break
        else:
          appExit('Daemon is not configured')
    # Initialize watching staff
    self._wTimer = Timer(500, self._eventHandler, par=False, start=True)
    self._tCnt = 0
    self._iNtfyWatcher = self._Watcher(self.config['dir'], self._eventHandler, par=True)
    # Set initial daemon status values
    self.vals = {'status': 'unknown', 'progress': '', 'laststatus': 'unknown', 'statchg': True,
                 'total': '...', 'used': '...', 'free': '...', 'trash': '...', 'szchg': True,
                 'error':'', 'path':'', 'lastitems': [], 'lastchg': True}
    # Check that daemon is running
    if self.getOutput() != '':                        # Is daemon running?
      self._iNtfyWatcher.start()        # Activate iNotify watcher
    else:                                             # Daemon is not running
      if self.config.get('startonstartofindicator', True):
        self.start()                    # Start daemon if it is required

  def _eventHandler(self, iNtf):        # Daemon event handler
    '''
    Handle iNotify and and Timer based events.
    After receiving and parsing the daemon output it raises outside change event if daemon changes
    at least one of its status values.
    It can be called by timer (when iNtf=False) or by iNonifier (when iNtf=True)
    '''

    # Parse fresh daemon output. Parsing returns true when something changed
    if self._parseOutput(self.getOutput()):
      logger.debug(self.ID + 'Event raised by' + ('iNtfy ' if iNtf else 'Timer '))
      self.change(self.vals)                  # Raise outside update event
    # --- Handle timer delays ---
    if iNtf:                                  # True means that it is called by iNonifier
      self._wTimer.update(2000)               # Set timer interval to 2 sec.
      self._tCnt = 0                          # Reset counter as it was triggered not by timer
    else:                                     # It called by timer
      if self.vals['status'] != 'busy':       # In 'busy' keep update interval (2 sec.)
        if self._tCnt < 9:                    # Increase interval up to 10 sec (2 + 8)
          self._wTimer.update((2 + self._tCnt) * 1000)
          self._tCnt += 1                     # Increase counter to increase delay next activation.
    return True                               # True is required to continue activations by timer.

  def change(self, vals):          # Redefined update handler
    logger.debug('Update values : %s' % str(vals))

  def getOutput(self, userLang=False):  # Get result of 'yandex-disk status'
    cmd = [self.YDC, '-c', self.config.fileName, 'status']
    if not userLang:      # Change locale settings when it required
      cmd = ['env', '-i', "LANG='en_US.UTF8'", "TMPDIR=%s"%tmpDir] + cmd
    try:
      output = check_output(cmd, universal_newlines=True)
    except:
      output = ''         # daemon is not running or bad
    # logger.debug('output = %s' % output)
    return output

  def _parseOutput(self, out):          # Parse the daemon output
    '''
    It parses the daemon output and check that something changed from last daemon status.
    The self.vals dictionary is updated with new daemon statuses and self.update set represents
    the changes in self.vals. It returns True is something changed

    Daemon status is converted form daemon raw statuses into internal representation.
    Internal status can be on of the following: 'busy', 'idle', 'paused', 'none', 'no_net', 'error'.
    Conversion is done by following rules:
     - empty status (daemon is not running) converted to 'none'
     - statuses 'busy', 'idle', 'paused' are passed 'as is'
     - 'index' is ignored (previous status is kept)
     - 'no internet access' converted to 'no_net'
     - 'error' covers all other errors, except 'no internet access'
    '''
    self.vals['statchg'] = False
    self.vals['szchg'] = False
    self.vals['lastchg'] = False
    # Split output on two parts: list of named values and file list
    output = out.split('Last synchronized items:')
    if len(output) == 2:
      files = output[1]
    else:
      files = ''
    output = output[0].splitlines()
    # Make a dictionary from named values (use only lines containing ':')
    res = dict([reFindall(r'\s*(.+):\s*(.*)', l)[0] for l in output if ':' in l])
    # Parse named status values
    for srch, key in (('Synchronization core status', 'status'), ('Sync progress', 'progress'),
                      ('Total', 'total'), ('Used', 'used'), ('Available', 'free'),
                      ('Trash size', 'trash'), ('Error', 'error'), ('Path', 'path')):
      val = res.get(srch, '')
      if key == 'status':                     # Convert status to internal representation
        # logger.debug('Raw status: \'%s\', previous status: %s'%(val, self.vals['status']))
        # Store previous status
        self.vals['laststatus'] = self.vals['status']
        # Convert daemon raw status to internal representation
        val = ('none' if val == '' else
               # Ignore index status
               'busy' if val == 'index' and self.vals['laststatus'] == "unknown" else
               self.vals['laststatus'] if val == 'index' and self.vals['laststatus'] != "unknown" else
               # Rename long error status
               'no_net' if val == 'no internet access' else
               # pass 'busy', 'idle' and 'paused' statuses 'as is'
               val if val in ['busy', 'idle', 'paused'] else
               # Status 'error' covers 'error', 'failed to connect to daemon process' and other.
               'error')
      elif key != 'progress' and val == '':   # 'progress' can be '' the rest - can't
        val = '...'                           # Make default filling for empty values
      # Check value change and store changed
      if self.vals[key] != val:               # Check change of value
        self.vals[key] = val                  # Store new value
        if key == 'status':
          self.vals['statchg'] = True         # Remember that status changed
        elif key == 'progress':
          self.vals['statchg'] = True         # Remember that progress changed
        else:
          self.vals['szchg'] = True           # Remember that something changed in sizes values
    # Parse last synchronized items
    buf = reFindall(r".*: '(.*)'\n", files)
    # Check if file list has been changed
    if self.vals['lastitems'] != buf:
      self.vals['lastitems'] = buf            # Store the new file list
      self.vals['lastchg'] = True             # Remember that it is changed
    # return True when something changed, if nothing changed - return False
    return self.vals['statchg'] or self.vals['szchg'] or self.vals['lastchg']

  def _errorDialog(self, err):          # Show error messages according to the error
    global logo
    logger.error('Daemon initialization failed: %s', err)
    if err == 'NOCONFIG' or err == 'CANTSTART':
      dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK_CANCEL,
                                 _('Yandex.Disk Indicator: daemon start failed'))
      if err == 'NOCONFIG':
        dialog.format_secondary_text(_('Yandex.Disk daemon failed to start because it is not' +
         ' configured properly\n  To configure it up: press OK button.\n  Press Cancel to exit.'))
      else:
        dialog.format_secondary_text(_('Yandex.Disk daemon failed to start.' +
         '\n  Press OK to continue without started daemon or Cancel to exit.'))
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
                                       'unrecognized error.'))
    dialog.set_default_size(400, 250)
    dialog.set_icon(logo)
    response = dialog.run()
    dialog.destroy()
    if err == 'NOCONFIG' and response == Gtk.ResponseType.OK:  # Launch Set-up utility
      logger.debug('starting configuration utility: %s' % pathJoin(installDir, 'ya-setup'))
      retCode = call([pathJoin(installDir, 'ya-setup'), self.config.fileName])
    elif err == 'CANTSTART' and response == Gtk.ResponseType.OK:
      retCode = 0
    else:
      retCode = 0 if err == 'NONET' else 1
    dialog.destroy()
    return retCode              # 0 when error is not critical or fixed (daemon has been configured)

  def start(self):                      # Execute 'yandex-disk start'
    '''
    Execute 'yandex-disk start' and return '' if success or error message if not
    ... but sometime it starts successfully with error message
    Additionally it starts iNotify monitoring in case of success start
    '''
    if self.getOutput() != "":
      logger.info('Daemon is already started')
      return
    try:                                          # Try to start
      msg = check_output([self.YDC, '-c', self.config.fileName, 'start'], universal_newlines=True)
      logger.info('Start success, message: %s' % msg)
    except CalledProcessError as e:
      logger.error('Daemon start failed:%s' % e.output)
      return
    self._iNtfyWatcher.start()    # Activate iNotify watcher

  def stop(self):                       # Execute 'yandex-disk stop'
    if self.getOutput() == "":
      logger.info('Daemon is already stopped')
      return
    try:
      msg = check_output([self.YDC, '-c', self.config.fileName, 'stop'],
                         universal_newlines=True)
      logger.info('Start success, message: %s' % msg)
    except:
      logger.info('Start failed')

  def exit(self):                       # Handle daemon/indicator closing
    self._iNtfyWatcher.stop()
    # Stop yandex-disk daemon if it is required by its configuration
    if self.vals['status'] != 'none' and self.config.get('stoponexitfromindicator', False):
      self.stop()
      logger.info('Demon %sstopped' % self.ID)

class Indicator(YDDaemon):      # Yandex.Disk appIndicator

  def __init__(self, path, ID):
    indicatorName = "yandex-disk-%s" % ID[1: -1]
    # Create indicator notification engine
    self.notify = Notification(_('Yandex.Disk ') + ID)
    # Setup icons theme
    self.setIconTheme(config['theme'])
    # Create timer object for icon animation support (don't start it here)
    self.timer = Timer(777, self._iconAnimation, start=False)
    # Create App Indicator
    self.ind = appIndicator.Indicator.new(indicatorName, self.icon['paused'],
                                          appIndicator.IndicatorCategory.APPLICATION_STATUS)
    self.ind.set_status(appIndicator.IndicatorStatus.ACTIVE)
    self.menu = self.Menu(self, ID)               # Create menu for daemon
    self.ind.set_menu(self.menu)                  # Attach menu to indicator
    # Initialize Yandex.Disk daemon connection object
    super(Indicator, self).__init__(path, ID)

  def change(self, vals):       # Redefinition of daemon class call-back function
    '''
    It handles daemon status changes by updating icon, creating messages and also update
    status information in menu (status, sizes and list of last synchronized items).
    It is called when daemon detects any change of its status.
    '''
    logger.info(self.ID + 'Change event: %s' % ','.join(['stat' if vals['statchg'] else '',
                                                         'size' if vals['szchg'] else '',
                                                         'last' if vals['lastchg'] else '']))
    # Update information in menu
    self.menu.update(vals, self.config['dir'])
    # Handle daemon status change 
    if vals['status'] != vals['laststatus'] or vals['laststatus'] =='unknown':
      logger.info('Status: ' + vals['laststatus'] + ' -> ' + vals['status'])
      self.updateIcon(vals['status'])     # Update icon
      # Create notifications for status change events
      if config['notifications']:
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

  def setIconTheme(self, theme):    # Determine paths to icons according to current theme
    global installDir, configPath
    theme = 'light' if theme else 'dark'
    # Determine theme from application configuration settings
    defaultPath = pathJoin(installDir, 'icons', theme)
    userPath = pathJoin(configPath, 'icons', theme)
    # Set appropriate paths to all status icons
    self.icon = dict()
    for status in ['idle', 'error', 'paused', 'none', 'no_net', 'busy']:
      name = ('yd-ind-pause.png' if status in {'paused', 'none', 'no_net'} else
              'yd-busy1.png' if status == 'busy' else
              'yd-ind-' + status + '.png')
      userIcon = pathJoin(userPath, name)
      self.icon[status] = userIcon if pathExists(userIcon) else pathJoin(defaultPath, name)
      # userIcon corresponds to busy icon on exit from this loop
    # Set theme paths according to existence of first busy icon
    self.themePath = userPath if pathExists(userIcon) else defaultPath

  def updateIcon(self, status):             # Change indicator icon according to just changed daemon status
    # Set icon according to the current status
    self.ind.set_icon(self.icon[status])
    # Handle animation
    if status == 'busy':                # Just entered into 'busy' status
      self._seqNum = 2                  # Next busy icon number for animation
      self.timer.start()                # Start animation timer
    elif self.timer.active:
      self.timer.stop()                 # Stop animation timer when status is not busy

  def _iconAnimation(self):         # Changes busy icon by loop (triggered by self.timer)
    # Set next animation icon
    self.ind.set_icon(pathJoin(self.themePath, 'yd-busy' + str(self._seqNum) + '.png'))
    # Calculate next icon number
    self._seqNum = self._seqNum % 5 + 1   # 5 icon numbers in loop (1-2-3-4-5-1-2-3...)
    return True                           # True required to continue triggering by timer

  class Menu(Gtk.Menu):             # Indicator menu

    def __init__(self, daemon, ID):
      self.daemon = daemon                      # Store reference to daemon object for future usage
      self.folder = ''
      Gtk.Menu.__init__(self)                   # Create menu
      self.ID = ID
      if self.ID != '':                         # Add addition field in multidaemon mode
        self.yddir = Gtk.MenuItem('');  self.yddir.set_sensitive(False);   self.append(self.yddir)
      self.status = Gtk.MenuItem();     self.status.connect("activate", self.showOutput)
      self.append(self.status)
      self.used = Gtk.MenuItem();       self.used.set_sensitive(False)
      self.append(self.used)
      self.free = Gtk.MenuItem();       self.free.set_sensitive(False)
      self.append(self.free)
      self.last = Gtk.MenuItem(_('Last synchronized items'))
      self.last.set_sensitive(False)
      self.lastItems = Gtk.Menu()               # Sub-menu: list of last synchronized files/folders
      self.last.set_submenu(self.lastItems)     # Add submenu (empty at the start)
      self.append(self.last)
      self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
      self.daemon_ss = Gtk.MenuItem('')         # Start/Stop daemon: Label is depends on current daemon status
      self.daemon_ss.connect("activate", self.startStopDaemon)
      self.append(self.daemon_ss)
      self.open_folder = Gtk.MenuItem(_('Open Yandex.Disk Folder'))
      self.open_folder.connect("activate", lambda w: self.openPath(w, self.folder))
      self.append(self.open_folder)
      open_web = Gtk.MenuItem(_('Open Yandex.Disk on the web'))
      open_web.connect("activate", self.openInBrowser, _('https://disk.yandex.com'))
      self.append(open_web)
      self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
      self.preferences = Gtk.MenuItem(_('Preferences'))
      self.preferences.connect("activate", Preferences)
      self.append(self.preferences)
      open_help = Gtk.MenuItem(_('Help'))
      m_help = Gtk.Menu()
      help1 = Gtk.MenuItem(_('Yandex.Disk daemon'))
      help1.connect("activate", self.openInBrowser, _('https://yandex.com/support/disk/'))
      m_help.append(help1)
      help2 = Gtk.MenuItem(_('Yandex.Disk Indicator'))
      help2.connect("activate", self.openInBrowser,
                _('https://github.com/slytomcat/yandex-disk-indicator/wiki/Yandex-disk-indicator'))
      m_help.append(help2)
      open_help.set_submenu(m_help)
      self.append(open_help)
      self.about = Gtk.MenuItem(_('About'));    self.about.connect("activate", self.openAbout)
      self.append(self.about)
      self.append(Gtk.SeparatorMenuItem.new())  # -----separator--------
      close = Gtk.MenuItem(_('Quit'))
      close.connect("activate", self.close)
      self.append(close)
      self.show_all()
      # Define user readable statuses dictionary
      self.YD_STATUS = {'idle': _('Synchronized'), 'busy': _('Sync.: '), 'none': _('Not started'),
                        'paused': _('Paused'), 'no_net': _('Not connected'), 'error': _('Error')}

    def update(self, vals, yddir):  # Update information in menu
      self.folder = yddir
      # Update status data
      if vals['statchg'] or vals['laststatus'] == 'unknown':
        self.status.set_label(_('Status: ') + self.YD_STATUS[vals['status']] +
                              (vals['progress'] if vals['status'] == 'busy'
                               else
                               ' '.join((':', vals['error'], shortPath(vals['path']))) if vals['status'] == 'error'
                               else
                               ''))
      # Update sizes data
      if vals['szchg'] or vals['laststatus'] == 'unknown':
        self.used.set_label(_('Used: ') + vals['used'] + '/' + vals['total'])
        self.free.set_label(_('Free: ') + vals['free'] + _(', trash: ') + vals['trash'])
      # Update last synchronized sub-menu when daemon is running
      if vals['lastchg'] or vals['laststatus'] == 'unknown':
        self.lastItems = Gtk.Menu()                  # New Sub-menu:
        #for widget in self.lastItems.get_children():  # Clear last synchronized sub-menu
        #  self.lastItems.remove(widget)
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
        self.last.set_sensitive(len(vals['lastitems']) != 0)
        logger.debug("Sub-menu 'Last synchronized' has " + str(len(vals['lastitems'])) + " items")
      # Update 'static' elements of menu
      if 'none' in (vals['status'], vals['laststatus']) or vals['laststatus'] == 'unknown':
        started = vals['status'] != 'none'
        self.status.set_sensitive(started)
        # zero-space UTF symbols are used to detect requered action without need to compare translated strings
        self.daemon_ss.set_label(('\u2060' + _('Stop Yandex.Disk daemon')) if started else ('\u200B' + _('Start Yandex.Disk daemon')))
        if self.ID != '':                             # Set daemon identity row in multidaemon mode
          self.yddir.set_label(self.ID + _('  Folder: ') + (shortPath(yddir) if yddir else '< NOT CONFIGURED >'))
        self.open_folder.set_sensitive(yddir != '') # Activate Open YDfolder if daemon configured
      self.show_all()                                 # Renew menu

    def openAbout(self, widget):            # Show About window
      global logo, indicators
      for i in indicators:
        i.menu.about.set_sensitive(False)           # Disable menu item
      aboutWindow = Gtk.AboutDialog()
      aboutWindow.set_logo(logo);   aboutWindow.set_icon(logo)
      aboutWindow.set_program_name(_('Yandex.Disk indicator'))
      aboutWindow.set_version(_('Version ') + appVer)
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
      for i in indicators:
        i.menu.about.set_sensitive(True)            # Enable menu item

    def showOutput(self, widget):           # Display daemon output in dialogue window
      global logo
      outText = self.daemon.getOutput(True)
      widget.set_sensitive(False)                         # Disable menu item
      statusWindow = Gtk.Dialog(_('Yandex.Disk daemon output message'))
      statusWindow.set_icon(logo)
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

    def openInBrowser(self, widget, url):   # Open URL
      openNewBrowser(url)

    def startStopDaemon(self, widget):      # Start/Stop daemon
      action = widget.get_label()[:1]
      # zero-space UTF symbols are used to detect requered action without need to compare translated strings
      if action == '\u200B':    # Start
        self.daemon.start()
      elif action == '\u2060':  # Stop
        self.daemon.stop()

    def openPath(self, widget, path):       # Open path
      logger.info('Opening %s' % path)
      if pathExists(path):
        try:
          call(['xdg-open', path])
        except:
          logger.error('Start of "%s" failed' % path)

    def close(self, widget):                # Quit from indicator
      appExit()

#### Application functions and classes
class Preferences(Gtk.Dialog):  # Preferences window of application and daemons

  class excludeDirsList(Gtk.Dialog):                                      # Excluded list dialogue

    def __init__(self, widget, parent, dcofig):   # show current list
      self.dconfig = dcofig
      self.parent = parent
      Gtk.Dialog.__init__(self, title=_('Folders that are excluded from synchronization'),
                          parent=parent, flags=1)
      self.set_icon(logo)
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
      self.dirset = [val for val in CVal(self.dconfig.get('exclude-dirs', None))]
      for val in self.dirset:
        self.exList.append([False, val])
      logger.debug(str(self.dirset))
      self.show_all()


    def exitFromDialog(self, widget):     # Save list from dialogue to "exclude-dirs" property
      if self.dconfig.changed:
        eList = CVal()                                      # Store path value from dialogue rows
        for i in self.dirset:
          eList.add(i)
        self.dconfig['exclude-dirs'] = eList.get()          # Save collected value
      logger.debug(str(self.dirset))
      self.destroy()                                        # Close dialogue

    def lineToggled(self, widget, path):  # Line click handler, it switch row selection
      self.exList[path][0] = not self.exList[path][0]

    def deleteSelected(self, widget):     # Remove selected rows from list
      listIiter = self.exList.get_iter_first()
      while listIiter is not None and self.exList.iter_is_valid(listIiter):
        if self.exList.get(listIiter, 0)[0]:
          self.dirset.remove(self.exList.get(listIiter, 1)[0])
          self.exList.remove(listIiter)
          self.dconfig.changed = True
        else:
          listIiter = self.exList.iter_next(listIiter)
      logger.debug(str(self.dirset))

    def addFolder(self, widget, parent):  # Add new path to list via FileChooserDialog
      dialog = Gtk.FileChooserDialog(_('Select catalogue to add to list'), parent,
                                     Gtk.FileChooserAction.SELECT_FOLDER,
                                     (_('Close'), Gtk.ResponseType.CANCEL,
                                      _('Select'), Gtk.ResponseType.ACCEPT))
      dialog.set_default_response(Gtk.ResponseType.CANCEL)
      rootDir = self.dconfig['dir']
      dialog.set_current_folder(rootDir)
      if dialog.run() == Gtk.ResponseType.ACCEPT:
        path = relativePath(dialog.get_filename(), start=rootDir)
        if path not in self.dirset:
          self.exList.append([False, path])
          self.dirset.append(path)
          self.dconfig.changed = True
      dialog.destroy()
      logger.debug(str(self.dirset))

  def __init__(self, widget):
    global config, indicators, logo
    # Preferences Window routine
    for i in indicators:
      i.menu.preferences.set_sensitive(False)   # Disable menu items to avoid multi-dialogs creation
    # Create Preferences window
    Gtk.Dialog.__init__(self, _('Yandex.Disk-indicator and Yandex.Disks preferences'), flags=1)
    self.set_icon(logo)
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
      cb.append(Gtk.CheckButton(msg))
      cb[-1].set_active(config[key])
      cb[-1].connect("toggled", self.onButtonToggled, cb[-1], key)
      preferencesBox.add(cb[-1])
    # --- End of Indicator preferences tab --- add it to notebook
    pref_notebook.append_page(preferencesBox, Gtk.Label(_('Indicator settings')))
    # Add daemos tabs
    for i in indicators:
      # --- Daemon start options tab ---
      optionsBox = Gtk.VBox(spacing=5)
      key = 'startonstartofindicator'           # Start daemon on indicator start
      cbStOnStart = Gtk.CheckButton(_('Start Yandex.Disk daemon %swhen indicator is starting')
                                    % i.ID)
      cbStOnStart.set_tooltip_text(_("When daemon was not started before."))
      cbStOnStart.set_active(i.config[key])
      cbStOnStart.connect("toggled", self.onButtonToggled, cbStOnStart, key, i.config)
      optionsBox.add(cbStOnStart)
      key = 'stoponexitfromindicator'           # Stop daemon on exit
      cbStoOnExit = Gtk.CheckButton(_('Stop Yandex.Disk daemon %son closing of indicator') % i.ID)
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
      cbRO = Gtk.CheckButton(_('Read-Only: Do not upload locally changed files to Yandex.Disk'))
      cbRO.set_tooltip_text(_("Locally changed files will be renamed if a newer version of this " +
                              "file appear in Yandex.Disk."))
      cbRO.set_active(i.config[key])
      key = 'overwrite'                         # Option Overwrite    # daemon config
      overwrite = Gtk.CheckButton(_('Overwrite locally changed files by files' +
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
      exListButton = Gtk.Button(_('Excluded folders List'))
      exListButton.set_tooltip_text(_("Folders in the list will not be synchronized."))
      exListButton.connect("clicked", self.excludeDirsList, self, i.config)
      framedBox.add(exListButton)
      # --- End of Daemon start options tab --- add it to notebook
      pref_notebook.append_page(optionsBox, Gtk.Label(_('Daemon %soptions') % i.ID))
    self.set_resizable(False)
    self.show_all()
    self.run()
    if config.changed:
      config.save()                             # Save app config
    for i in indicators:
      if i.config.changed:
        i.config.save()                         # Save daemon options in config file
      i.menu.preferences.set_sensitive(True)    # Enable menu items
    self.destroy()

  def onButtonToggled(self, widget, button, key, dconfig=None, ow=None):  # Handle clicks
    toggleState = button.get_active()
    logger.debug('Togged: %s  val: %s' % (key, str(toggleState)))
    # Update configurations
    if key in ['read-only', 'overwrite', 'startonstartofindicator', 'stoponexitfromindicator']:
      dconfig[key] = toggleState                # Update daemon config
      dconfig.changed = True
    else:
      config.changed = True                     # Update application config
      config[key] = toggleState
    if key == 'theme':
        for i in indicators:                    # Update all indicators' icons
          i.setIconTheme(toggleState)           # Update icon theme
          i.updateIcon(i.vals['status'])        # Update current icon
    elif key == 'autostart':
      if toggleState:
        copyFile(autoStartSrc, autoStartDst)
      else:
        deleteFile(autoStartDst)
    elif key == 'fmextensions':
      if not button.get_inconsistent():         # It is a first call
        if not activateActions(toggleState):               # When activation/deactivation is not success:
          notify.send(_('ERROR in setting up of file manager extensions'))
          toggleState = not toggleState         # revert settings back
          button.set_inconsistent(True)         # set inconsistent state to detect second call
          button.set_active(toggleState)        # set check-button to reverted status
          # set_active will raise again the 'toggled' event
      else:                                     # This is a second call
        button.set_inconsistent(False)          # Just remove inconsistent status
    elif key == 'read-only':
      ow.set_sensitive(toggleState)

def appExit(msg=None):          # Exit from application (it closes all indicators)
  global indicators
  for i in indicators:
    i.exit()
  sysExit(msg)

def activateActions(activate):  # Install/deinstall file extensions
  result = False
  try:                  # Catch all exceptions during FM action activation/deactivation

    # Package manager check
    if call("hash dpkg>/dev/null 2>&1", shell=True) == 0:
      logger.info("dpkg detected")
      pm = 'dpkg -s '
    elif call("hash rpm>/dev/null 2>&1", shell=True) == 0:
      logger.info("rpm detected")
      pm = 'rpm -qi '
    elif call("hash pacman>/dev/null 2>&1", shell=True) == 0:
      logger.info("Pacman detected")
      pm = 'pacman -Qi '
    elif call("hash zypper>/dev/null 2>&1", shell=True) == 0:
      logger.info("Zypper detected")
      pm = 'zypper info '
    elif call("hash emerge>/dev/null 2>&1", shell=True) == 0:
      logger.info("Emerge detected")
      pm = 'which '
    else:
      logger.info("Your package manager is not supported. Automatic installation of FM extensions is not possible.")
      return result

    # --- Actions for Nautilus ---
    if call([pm + "nautilus>/dev/null 2>&1"], shell=True) == 0:
      logger.info("Nautilus installed")
      ver = check_output(["lsb_release -r | sed -n '1{s/[^0-9]//g;p;q}'"], shell=True)
      if ver != '' and int(ver) < 1210:
        nautilusPath = ".gnome2/nautilus-scripts/"
      else:
        nautilusPath = ".local/share/nautilus/scripts"
      logger.debug(nautilusPath)
      if activate:      # Install actions for Nautilus

        copyFile(pathJoin(installDir, "fm-actions/Nautilus_Nemo/publish"),
                 pathJoin(userHome, nautilusPath, _("Publish via Yandex.Disk")))
        copyFile(pathJoin(installDir, "fm-actions/Nautilus_Nemo/unpublish"),
                 pathJoin(userHome, nautilusPath, _("Unpublish from Yandex.disk")))
        result = True
      else:             # Remove actions for Nautilus
        deleteFile(pathJoin(userHome, nautilusPath, _("Publish via Yandex.Disk")))
        deleteFile(pathJoin(userHome, nautilusPath, _("Unpublish from Yandex.disk")))
        result = True

    # --- Actions for Nemo ---
    if call([pm + "nemo>/dev/null 2>&1"], shell=True) == 0:
      logger.info("Nemo installed")
      if activate:      # Install actions for Nemo
        copyFile(pathJoin(installDir, "fm-actions/Nautilus_Nemo/publish"),
                 pathJoin(userHome, ".local/share/nemo/scripts", _("Publish via Yandex.Disk")))
        copyFile(pathJoin(installDir, "fm-actions/Nautilus_Nemo/unpublish"),
                 pathJoin(userHome, ".local/share/nemo/scripts", _("Unpublish from Yandex.disk")))
        result = True
      else:             # Remove actions for Nemo
        deleteFile(pathJoin(userHome, ".gnome2/nemo-scripts", _("Publish via Yandex.Disk")))
        deleteFile(pathJoin(userHome, ".gnome2/nemo-scripts", _("Unpublish from Yandex.disk")))
        result = True

    # --- Actions for Thunar ---
    if call([pm + "thunar>/dev/null 2>&1"], shell=True) == 0:
      logger.info("Thunar installed")
      ucaPath = pathJoin(userHome, ".config/Thunar/uca.xml")
      # Read uca.xml
      with open(ucaPath) as ucaf:
        [(ust, actions, uen)] = reFindall(r'(^.*<actions>)(.*)(<\/actions>)', ucaf.read(), reS)
      acts = reFindall(r'(<action>.*?<\/action>)', actions, reS)
      nActs = dict((reFindall(r'<name>(.+?)<\/name>', u, reS)[0], u) for u in acts)

      if activate:      # Install actions for Thunar
        if _("Publish via Yandex.Disk") not in nActs.keys():
          nActs[_("Publish via Yandex.Disk")] = ("<action><icon>folder-publicshare</icon>" +
                           '<name>' + _("Publish via Yandex.Disk") +
                           '</name><command>yandex-disk publish %f | xclip -filter -selection' +
                           ' clipboard; zenity --info ' +
                           '--window-icon=/usr/share/yd-tools/icons/yd-128.png ' +
                           '--title="Yandex.Disk" --ok-label="' + _('Close') + '" --text="' +
                           _('URL to file: %f was copied into clipboard.') +
                           '"</command><description/><patterns>*</patterns>' +
                           '<directories/><audio-files/><image-files/><other-files/>' +
                           "<text-files/><video-files/></action>")
        if _("Unpublish from Yandex.disk") not in nActs.keys():
          nActs[_("Unpublish from Yandex.disk")] = ("<action><icon>folder</icon><name>" +
                           _("Unpublish from Yandex.disk") +
                           '</name><command>zenity --info ' +
                           '--window-icon=/usr/share/yd-tools/icons/yd-128_g.png --ok-label="' +
                           _('Close') + '" --title="Yandex.Disk" --text="' +
                           _("Unpublish from Yandex.disk") +
                           ': `yandex-disk unpublish %f`"</command>' +
                           '<description/><patterns>*</patterns>' +
                           '<directories/><audio-files/><image-files/><other-files/>' +
                           "<text-files/><video-files/></action>")

      else:             # Remove actions for Thunar
        if _("Publish via Yandex.Disk") in nActs.keys():
          del nActs[_("Publish via Yandex.Disk")]
        if _("Unpublish from Yandex.disk") in nActs.keys():
          del nActs[_("Unpublish from Yandex.disk")]

      # Save uca.xml
      with open(ucaPath, 'wt') as ucaf:
        ucaf.write(ust + ''.join(u for u in nActs.values()) + uen)
      result = True

    # --- Actions for Dolphin ---
    if call([pm + "dolphin>/dev/null 2>&1"], shell=True) == 0:
      logger.info("Dolphin installed")
      if activate:      # Install actions for Dolphin
        makeDirs(pathJoin(userHome, '.local/share/kservices5/ServiceMenus'))
        copyFile(pathJoin(installDir, "fm-actions/Dolphin/ydpublish.desktop"),
                 pathJoin(userHome, ".local/share/kservices5/ServiceMenus/ydpublish.desktop"))
        result = True
      else:             # Remove actions for Dolphin
        deleteFile(pathJoin(userHome, ".local/share/kservices5/ServiceMenus/ydpublish.desktop"))
        result = True

    # --- Actions for Pantheon-files ---
    if call([pm + "pantheon-files>/dev/null 2>&1"], shell=True) == 0:
      logger.info("Pantheon-files installed")
      ctrs_path = "/usr/share/contractor/"
      if activate:      # Install actions for Pantheon-files
        src_path = pathJoin(installDir, "fm-actions", "pantheon-files")
        ctr_pub = pathJoin(src_path, "yandex-disk-indicator-publish.contract")
        ctr_unpub = pathJoin(src_path, "yandex-disk-indicator-unpublish.contract")
        res = call(["gksudo", "-D", "yd-tools", "cp", ctr_pub, ctr_unpub, ctrs_path])
        if res == 0:
          result = True
        else:
          logger.error("Cannot enable actions for Pantheon-files")
      else:             # Remove actions for Pantheon-files
        res = call(["gksudo", "-D", "yd-tools", "rm",
                    pathJoin(ctrs_path, "yandex-disk-indicator-publish.contract"),
                    pathJoin(ctrs_path, "yandex-disk-indicator-unpublish.contract")])
        if res == 0:
          result = True
        else:
          logger.error("Cannot disable actions for Pantheon-files")

    # --- Actions for Caja ---
    if call([pm + "caja>/dev/null 2>&1"], shell=True) == 0:
      logger.info("Caja installed")
      if activate:      # Install actions for Nemo
        copyFile(pathJoin(installDir, "fm-actions/Nautilus_Nemo/publish"),
                 pathJoin(userHome, ".config/caja/scripts", _("Publish via Yandex.Disk")))
        copyFile(pathJoin(installDir, "fm-actions/Nautilus_Nemo/unpublish"),
                 pathJoin(userHome, ".config/caja/scripts", _("Unpublish from Yandex.disk")))
        result = True
      else:             # Remove actions for Nemo
        deleteFile(pathJoin(userHome, ".config/caja/scripts", _("Publish via Yandex.Disk")))
        deleteFile(pathJoin(userHome, ".config/caja/scripts", _("Unpublish from Yandex.disk")))
        result = True

  except Exception as e:
    logger.error("The following error occurred during the FM actions activation:\n %s" % str(e))
  return result

def argParse():                 # Parse command line arguments
  parser = ArgumentParser(description=_('Desktop indicator for yandex-disk daemon'), add_help=False)
  group = parser.add_argument_group(_('Options'))
  group.add_argument('-l', '--log', type=int, choices=range(10, 60, 10), dest='level', default=30,
            help=_('Sets the logging level: ' +
                   '10 - to show all messages (DEBUG), ' +
                   '20 - to show all messages except debugging messages (INFO), ' +
                   '30 - to show all messages except debugging and info messages (WARNING), ' +
                   '40 - to show only error and critical messages (ERROR), ' +
                   '50 - to show critical messages only (CRITICAL). Default: 30'))
  group.add_argument('-c', '--config', dest='cfg', metavar='path', default='',
            help=_('Path to configuration file of YandexDisk daemon. ' +
                   'This daemon will be added to daemons list' +
                   ' if it is not in the current configuration.' +
                   'Default: \'\''))
  group.add_argument('-r', '--remove', dest='rcfg', metavar='path', default='',
            help=_('Path to configuration file of daemon that should be removed' +
                   ' from daemos list. Default: \'\''))
  group.add_argument('-h', '--help', action='help', help=_('Show this help message and exit'))
  group.add_argument('-v', '--version', action='version', version='%(prog)s v.' + appVer,
            help=_('Print version and exit'))
  return parser.parse_args()

def checkAutoStart(path):       # Check that auto-start is enabled
  if pathExists(path):
    i = 1 if getenv('XDG_CURRENT_DESKTOP') in ('Unity', 'Pantheon') else 0
    with open(path, 'rt') as f:
      attr = reFindall(r'\nHidden=(.+)|\nX-GNOME-Autostart-enabled=(.+)', f.read())
      if attr:
        if attr[0][i] and attr[0][i] == ('true' if i else 'false'):
          return True
      else:
        return True
  return False

def setProcName(newname):
  from ctypes import cdll, byref, create_string_buffer
  libc = cdll.LoadLibrary('libc.so.6')
  buff = create_string_buffer(len(newname) + 1)
  buff.value = bytes(newname, 'UTF8')
  libc.prctl(15, byref(buff), 0, 0, 0)

###################### MAIN #########################
if __name__ == '__main__':
  # Application constants
  appName = 'yandex-disk-indicator'
  # See appVer in the beginnig of the code
  appHomeName = 'yd-tools'
  # Check for already running instance of the indicator application
  userHome = getenv("HOME")
  installDir = pathJoin('/usr/share', appHomeName)
  logo = Pixbuf.new_from_file(pathJoin(installDir, 'icons/yd-128.png'))
  configPath = pathJoin(userHome, '.config', appHomeName)
  tmpDir = getenv("TMPDIR")
  if tmpDir is None:
    tmpDir = '/tmp'
  # Define .desktop files locations for indicator auto-start facility
  autoStartSrc = '/usr/share/applications/Yandex.Disk-indicator.desktop'
  autoStartDst = pathJoin(userHome, '.config/autostart/Yandex.Disk-indicator.desktop')

  # Initialize logging
  basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s')
  logger = getLogger('')

  # Setup localization
  # Load translation object (or NullTranslations) and define _() function.
  translation(appName, '/usr/share/locale', fallback=True).install()

  # Get command line arguments or their default values
  args = argParse()

  # Change the process name
  setProcName(appHomeName)

  # Check for already running instance of the indicator application
  if (str(getpid()) !=
      check_output(["pgrep", '-u', str(geteuid()), "yd-tools"], universal_newlines=True).strip()):
    sysExit(_('The indicator instance is already running.'))

  # Set user specified logging level
  logger.setLevel(args.level)

  # Report app version and logging level
  logger.info('%s v.%s' % (appName, appVer))
  logger.debug('Logging level: ' + str(args.level))

  # Application configuration
  '''
  User configuration is stored in ~/.config/<appHomeName>/<appName>.conf file.
  This file can contain comments (line starts with '#') and config values in
  form: key=value[,value[,value ...]] where keys and values can be quoted ("...") or not.
  The following key words are reserved for configuration:
    autostart, notifications, theme, fmextensions and daemons.

  The dictionary 'config' stores the config settings for usage in code. Its values are saved to
  config file on exit from the Menu.Preferences dialogue or when there is no configuration file
  when application starts.

  Note that daemon settings ('dir', 'read-only', 'overwrite' and 'exclude_dir') are stored
  in ~/ .config/yandex-disk/config.cfg file. They are read in YDDaemon.__init__() method
  (in dictionary YDDaemon.config). Their values are saved to daemon config file also
  on exit from Menu.Preferences dialogue.

  Additionally 'startonstartofindicator' and 'stoponexitfromindicator' values are added into daemon
  configuration file to provide the functionality of obsolete 'startonstart' and 'stoponexit'
  values for each daemon individually.
  '''
  config = Config(pathJoin(configPath, appName + '.conf'))
  # Read some settings to variables, set default values and update some values
  config['autostart'] = checkAutoStart(autoStartDst)
  # Setup on-screen notification settings from config value
  config.setdefault('notifications', True)
  config.setdefault('theme', False)
  config.setdefault('fmextensions', True)
  config.setdefault('daemons', '~/.config/yandex-disk/config.cfg')
  # Is it a first run?
  if not config.readSuccess:
    logger.info('No config, probably it is a first run.')
    # Create application config folders in ~/.config
    try:
      makeDirs(configPath)
      makeDirs(pathJoin(configPath, 'icons/light'))
      makeDirs(pathJoin(configPath, 'icons/dark'))
      # Copy icon themes readme to user config catalogue
      copyFile(pathJoin(installDir, 'icons/readme'), pathJoin(configPath, 'icons/readme'))
    except:
      sysExit('Can\'t create configuration files in %s' % configPath)
    # Activate indicator automatic start on system start-up
    if not pathExists(autoStartDst):
      try:
        makeDirs(pathJoin(userHome, '.config/autostart'))
        copyFile(autoStartSrc, autoStartDst)
        config['autostart'] = True
      except:
        logger.error('Can\'t activate indicator automatic start on system start-up')

    # Activate FM actions according to config (as it is first run)
    activateActions(config['fmextensions'])
    # Default settings should be saved (later)
    config.changed = True

  # Add new daemon if it is not in current list
  daemons = [expanduser(d) for d in CVal(config['daemons'])]
  if args.cfg:
    args.cfg = expanduser(args.cfg)
    if args.cfg not in daemons:
      daemons.append(args.cfg)
      config.changed = True
  # Remove daemon if it is in the current list
  if args.rcfg:
    args.rcfg = expanduser(args.rcfg)
    if args.rcfg in daemons:
      daemons.remove(args.rcfg)
      config.changed = True
  # Check that at least one daemon is in the daemons list
  if not daemons:
    sysExit(_('No daemons specified.\nCheck correctness of -r and -c options.'))
  # Update config if daemons list has been changed
  if config.changed:
    config['daemons'] = CVal(daemons).get()
    # Update configuration file
    config.save()

  # Make indicator objects for each daemon in daemons list
  indicators = []
  for d in daemons:
    indicators.append(Indicator(d.replace('~', userHome),
                                _('#%d ') % len(indicators) if len(daemons) > 1 else ''))

  # Register the SIGTERM handler for graceful exit when indicator is killed
  signal(SIGTERM, lambda _signo, _stack_frame: appExit())

  # Start GTK Main loop
  Gtk.main()
