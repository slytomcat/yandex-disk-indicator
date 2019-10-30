#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from tools import Config, CVal, check_output, reFindall, pathExists, pathJoin, getLogger

from os import stat
from os.path import expanduser
from shutil import which
from threading import Timer as thTimer, Lock, Thread
from tempfile import gettempdir
from sys import exit as sysExit
from subprocess import CalledProcessError


LOGGER = getLogger('')

#################### Main daemon class ####################
class YDDaemon:                 # Yandex.Disk daemon interface
  """
  This is the fully automated class that serves as daemon interface.
  Public methods:
  __init__ - Handles initialization of the object and as a part - auto-start daemon if it
             is required by configuration settings.
  output   - Provides daemon output (in user language) through the parameter of callback. Executed in separate thread
  start    - Request to start daemon. Do nothing if it is alreday started. Executed in separate thread
  stop     - Request to stop daemon. Do nothing if it is not started. Executed in separate thread
  exit     - Handles 'Stop on exit' facility according to daemon configuration settings.
  change   - Virtual method for handling daemon status changes. It have to be redefined by UI class.
             The parameters of the call - status values dictionary with following keys:
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
  error    - Virtual method for error handling. It have to be redefined by UI class.

  Class interface variables:
  ID       - the daemon identity string (empty in single daemon configuration)
  config   - The daemon configuration dictionary (object of _DConfig(Config) class)
  """
  #################### Virtual methods ##################
  # they have to be implemented in GUI part of code

  def error(self, errStr, cfgPath):
    """ Error handler """
    LOGGER.debug('%sError %s , path %s', self.ID, errStr, cfgPath)
    return 0

  def change(self, vals):
    """ Updates handler """
    LOGGER.debug('%sUpdate event: %s',  self.ID, str(vals))

  #################### Private classes ####################
  class __Watcher:
    """ File changes watcher implementation """
    def __init__(self, path, handler, *args, **kwargs):
      self.path = path
      self.handler = handler
      self.args = args
      self.kwargs = kwargs
      # Don't start timer initially
      self.status = False
      self.mark = None
      self.timer = None

    def start(self):                    # Activate iNotify watching
      if self.status:
        return
      if not pathExists(self.path):
        LOGGER.info("Watcher was not started: path '%s' was not found.", self.path)
        return
      self.mark = stat(self.path).st_ctime_ns

      def wHandler():
        st = stat(self.path).st_ctime_ns
        if st != self.mark:
          self.mark = st
          self.handler(*self.args, **self.kwargs)
        self.timer = thTimer(0.5, wHandler)
        self.timer.start()

      self.timer = thTimer(0.5, wHandler)
      self.timer.start()
      self.status = True

    def stop(self):
      if not self.status:
        return
      self.timer.cancel()

  class __DConfig(Config):
    """ Redefined class for daemon config """

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
                                    ', '.join(v for v in CVal(exList)))
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
      return False

  #################### Private methods ####################
  def __init__(self, cfgFile, ID):         # Check that daemon installed and configured and initialize object
    """
    cfgFile  - full path to config file
    ID       - identity string '#<n> ' in multi-instance environment or
               '' in single instance environment"""
    self.ID = ID                                      # Remember daemon identity
    self.__YDC = which('yandex-disk')
    if self.__YDC is None:
      self.error('', '')
      exit(1)
    # Try to read Yandex.Disk configuration file and make sure that it is correctly configured
    self.config = self.__DConfig(cfgFile, load=False)
    while True:
      # Check the daemon configuration and prepare error message according the detected problem
      if not self.config.load():
        errorStr = "Error: the file %s is missing or has wrong structre" % cfgFile
      else:
        d = self.config.get('dir', "")
        a = self.config.get('auth', "")
        if not d or not a:
          errorStr = ("Error: " + ("option 'dir'" if not d else "") + (" and " if not d and not a else "") +
            ("option 'auth'" if not a else "") + (" are " if not a and not d else " is ") +
            "missing in the daemon configuration file %s" % cfgFile)
        else:
          dp = expanduser(d)
          dne = not pathExists(dp)
          ap = expanduser(a)
          ane = not pathExists(ap)
          if ane or dne:
            errorStr = ("Error: " + ("path %s" % dp if dne else "") + (" and " if dne and ane else "") +
              ("path %s" % ap if ane else "") + (" are " if ane and dne else " is ") + "not exist")
          else:
            break # no config problems was found, go on
      # some configuration problem was found and errorStr contains the detailed description of the problem
      if self.error(errorStr, cfgFile) != 0:
        if ID != '':
          self.config['dir'] = ""
          break   # Exit from loop in multi-instance configuration
        else:
          sysExit('Daemon is not configured')
    self.tmpDir = gettempdir()
    # Set initial daemon status values
    self.__v = {'status': 'unknown', 'progress': '', 'laststatus': 'unknown', 'statchg': True,
                'total': '...', 'used': '...', 'free': '...', 'trash': '...', 'szchg': True,
                'error': '', 'path': '', 'lastitems': [], 'lastchg': True}
    # Declare event handler staff for callback from watcher and timer
    self.__tCnt = 0                          # Timer event counter
    self.__lock = Lock()                     # event handler lock

    def eventHandler(watch):
      """
      Handles watcher (when watch=False) and and timer (when watch=True) events.
      After receiving and parsing the daemon output it raises outside change event if daemon changes
      at least one of its status values.
      """
      # Enter to critical section through acquiring of the lock as it can be called from two different threads
      self.__lock.acquire()
      # Parse fresh daemon output. Parsing returns true when something changed
      if self.__parseOutput(self.__getOutput()):
        LOGGER.debug('%sEvent raised by %s', self.ID, (' Watcher' if watch else ' Timer'))
        self.change(self.__v)                # Call the callback of update event handler
      # --- Handle timer delays ---
      self.__timer.cancel()                  # Cancel timer if it still active
      if watch or self.__v['status'] == 'busy':
        delay = 2                            # Initial delay
        self.__tCnt = 0                      # Reset counter
      else:                                  # It called by timer
        delay = 2 + self.__tCnt              # Increase interval up to 10 sec (2 + 8)
        self.__tCnt += 1                     # Increase counter to increase delay next activation.
      if self.__tCnt < 9:                    # Don't start timer after 10 seconds delay
        self.__timer = thTimer(delay, eventHandler, (False,))
        self.__timer.start()
      # Leave the critical section
      self.__lock.release()

    # Initialize watcher staff
    self.__watcher = self.__Watcher(pathJoin(expanduser(self.config['dir']), '.sync/cli.log'), eventHandler, (True,))
    # Initialize timer staff
    self.__timer = thTimer(0.3, eventHandler, (False,))
    self.__timer.start()

    # Start daemon if it is required in configuration
    if self.config.get('startonstartofindicator', True):
      self.start()
    else:
      self.__watcher.start()             # try to activate file watcher

  def __getOutput(self, userLang=False):   # Get result of 'yandex-disk status'
    cmd = [self.__YDC, '-c', self.config.fileName, 'status']
    if not userLang:      # Change locale settings when it required
      cmd = ['env', '-i', "TMPDIR=%s" % self.tmpDir] + cmd
    # LOGGER.debug('cmd = %s', str(cmd))
    try:
      output = check_output(cmd, universal_newlines=True)
    except:
      output = ''         # daemon is not running or bad
      # LOGGER.debug('Status output = %s', output)
    return output

  def __parseOutput(self, out):            # Parse the daemon output
    """
    It parses the daemon output and check that something changed from last daemon status.
    The self.__v dictionary is updated with new daemon statuses. It returns True is something changed
    Daemon status is converted form daemon raw statuses into internal representation.
    Internal status can be on of the following: 'busy', 'idle', 'paused', 'none', 'no_net', 'error'.
    Conversion is done by following rules:
     - empty status (daemon is not running) converted to 'none'
     - statuses 'busy', 'idle', 'paused' are passed 'as is'
     - 'index' is ignored (previous status is kept)
     - 'no internet access' converted to 'no_net'
     - 'error' covers all other errors, except 'no internet access'
    """
    self.__v['statchg'] = False
    self.__v['szchg'] = False
    self.__v['lastchg'] = False
    # Split output on two parts: list of named values and file list
    output = out.split('Last synchronized items:')
    if len(output) == 2:
      files = output[1]
    else:
      files = ''
    output = output[0].splitlines()
    # Make a dictionary from named values (use only lines containing ':')
    res = dict(reFindall(r'\s*(.+):\s*(.*)', l)[0] for l in output if ':' in l)
    # Parse named status values
    for srch, key in (('Synchronization core status', 'status'), ('Sync progress', 'progress'),
                      ('Total', 'total'), ('Used', 'used'), ('Available', 'free'),
                      ('Trash size', 'trash'), ('Error', 'error'), ('Path', 'path')):
      val = res.get(srch, '')
      if key == 'status':                     # Convert status to internal representation
        # LOGGER.debug('Raw status: \'%s\', previous status: %s', val, self.__v['status'])
        # Store previous status
        self.__v['laststatus'] = self.__v['status']
        # Convert daemon raw status to internal representation
        val = ('none' if val == '' else
               # Ignore index status
               'busy' if val == 'index' and self.__v['laststatus'] == "unknown" else
               self.__v['laststatus'] if val == 'index' and self.__v['laststatus'] != "unknown" else
               # Rename long error status
               'no_net' if val == 'no internet access' else
               # pass 'busy', 'idle' and 'paused' statuses 'as is'
               val if val in ['busy', 'idle', 'paused'] else
               # Status 'error' covers 'error', 'failed to connect to daemon process' and other.
               'error')
      elif key != 'progress' and val == '':   # 'progress' can be '' the rest - can't
        val = '...'                           # Make default filling for empty values
      # Check value change and store changed
      if self.__v[key] != val:                # Check change of value
        self.__v[key] = val                   # Store new value
        if key == 'status':
          self.__v['statchg'] = True          # Remember that status changed
        elif key == 'progress':
          self.__v['statchg'] = True          # Remember that progress changed
        else:
          self.__v['szchg'] = True            # Remember that something changed in sizes values
    # Parse last synchronized items
    buf = reFindall(r".*: '(.*)'\n", files)
    # Check if file list has been changed
    if self.__v['lastitems'] != buf:
      self.__v['lastitems'] = buf             # Store the new file list
      self.__v['lastchg'] = True              # Remember that it is changed
    # return True when something changed, if nothing changed - return False
    return self.__v['statchg'] or self.__v['szchg'] or self.__v['lastchg']

  #################### Interface methods ####################
  def output(self, callBack):              # Receive daemon output in separate thread and pass it back through the callback
    Thread(target=lambda: callBack(self.__getOutput(True))).start()

  def start(self, wait=False):             # Execute 'yandex-disk start' in separate thread
    """
    Execute 'yandex-disk start' in separate thread
    Additionally it starts watcher in case of success start
    """
    def do_start():
      if self.__getOutput() != "":
        LOGGER.info('Daemon is already started')
        self.__watcher.start()    # Activate file watcher
        return
      try:                        # Try to start
        msg = check_output([self.__YDC, '-c', self.config.fileName, 'start'], universal_newlines=True)
        LOGGER.info('Daemon started, message: %s', msg)
      except CalledProcessError as e:
        LOGGER.error('Daemon start failed: %s', e.output)
        return
      self.__watcher.start()      # Activate file watcher
    if wait:
      do_start()
    else:
      Thread(target=do_start).start()

  def stop(self, wait=False):              # Execute 'yandex-disk stop' in separate thread
    def do_stop():
      if self.__getOutput() == "":
        LOGGER.info('Daemon is not started')
        return
      try:
        msg = check_output([self.__YDC, '-c', self.config.fileName, 'stop'], universal_newlines=True)
        LOGGER.info('Daemon stopped, message: %s', msg)
      except:
        LOGGER.info('Daemon stop failed')
    if wait:
      do_stop()
    else:
      Thread(target=do_stop).start()

  def exit(self):                          # Handle daemon/indicator closing
    LOGGER.debug("Indicator %sexit started: ", self.ID)
    self.__watcher.stop()
    self.__timer.cancel()  # stop event timer if it is running
    # Stop yandex-disk daemon if it is required by its configuration
    if self.config.get('stoponexitfromindicator', False):
      self.stop(wait=True)
      LOGGER.info('Demon %sstopped', self.ID)
    LOGGER.debug('Indicator %sexited', self.ID)
