#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from os import remove, makedirs, getenv, getpid, geteuid
from argparse import ArgumentParser
from logging import getLogger
from shutil import copy as fileCopy, which
from os.path import exists as pathExists, join as pathJoin, relpath as relativePath, expanduser
from subprocess import check_output, CalledProcessError, call
from re import findall as reFindall, sub as reSub, search as reSearch, M as reM, S as reS
from sys import exit as sysExit

from logging import getLogger
LOGGER = getLogger('')

# define fake gettext
_ = lambda x:x

#################### Common utility functions and classes ####################
def copyFile(src, dst):
  '''File copy functiion'''
  try:
    fileCopy(src, dst)
  except:
    LOGGER.error("File Copy Error: from %s to %s", src, dst)

def deleteFile(dst):
  '''Delete file function'''
  try:
    remove(dst)
  except:
    LOGGER.error('File Deletion Error: %s', dst)

def makeDirs(dst):
  '''Create all child directories up to specified'''
  try:
    makedirs(dst, exist_ok=True)
  except:
    LOGGER.error('Dirs creation Error: %s', dst)

def shortPath(path):
  '''Make short path to display it'''
  return (path[: 20] + '...' + path[-27:] if len(path) > 50 else path).replace('_', '\u02CD')

class CVal:                     # Multivalue helper
  ''' Class to work with value that can be None, scalar item or list of items depending
      of number of elementary items added to it or it contain. '''

  def __init__(self, initialValue=None):
    self.set(initialValue)   # store initial value
    self.index = None

  def get(self):                  
    # Just returns the current value of cVal
    return self.val

  def set(self, value):           
    """ Set internal value """
    self.val = value
    if isinstance(self.val, list) and len(self.val) == 1:
      self.val = self.val[0]
    return self.val

  def add(self, item):            
    """ Add item """
    if isinstance(self.val, list):  # Is it third, fourth ... value?
      self.val.append(item)         # Just append new item to list
    elif self.val is None:          # Is it first item?
      self.val = item               # Just store item
    else:                           # It is the second item.
      self.val = [self.val, item]   # Convert scalar value to list of items.
    return self.val

  def __iter__(self):             
    """ cVal iterator object initialization """
    if isinstance(self.val, list):  # Is CVal a list?
      self.index = -1
    elif self.val is None:          # Is CVal not defined?
      self.index = None
    else:                           # CVal is scalar type.
      self.index = -2
    return self

  def __next__(self):             
    """ cVal iterator support """
    if self.index is None:            # Is CVal not defined?
      raise StopIteration             # Stop iterations
    self.index += 1
    if self.index >= 0:               # Is CVal a list?
      if self.index < len(self.val):  # Is there a next element in list?
        return self.val[self.index]
      self.index = None               # There is no more elements in list.
      raise StopIteration             # Stop iterations
    else:                             # CVal has scalar type.
      self.index = None               # Remember that there is no more iterations possible
      return self.val

  def __bool__(self):
    """ returns False for empty cVal oterways returns True """ 
    return self.val is not None

class Config(dict):             
  """ Configuration is a class to represent stored on disk configuration values """

  def __init__(self, fileName, load=True,
               bools=None, boolval=None,
               usequotes=True, delimiter='='):
    bools = [['true', 'yes', 'y'], ['false', 'no', 'n']] if  bools is None else bools
    boolval=['yes', 'no'] if boolval is None else boolval
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
      if st.startswith(','):                      # String is continued with comma?
        st = st[1:].lstrip()                      # Remove comma and following spaces
        if st != '':                              # String is continued after comma?
          continue                                # Continue to search values
        # else:                                   # Error: No value after comma
      # else:                                     # Error: Next symbol is not comma
      return None                                 # Error

  def load(self):
    """
    Reads config file to dictionary.
    Config file should contain key=value rows.
    Key can be quoted or not.
    Value can be one item or list of comma-separated items. Each value item can be quoted or not.
    When value is a single item then it creates key:value item in dictionary
    When value is a list of items it creates key:[value, value,...] dictionary's item.
    """
    try:                              # Read configuration file into list of tuples ignoring blank
                                      # lines, lines without delimiter, and lines with comments.
      with open(self.fileName) as cf:
        res = [reFindall(r'^\s*(.+?)\s*%s\s*(.*)$' % self.delimiter, l)[0]
               for l in cf if l and self.delimiter in l and l.lstrip()[0] != '#']
      self.readSuccess = True
    except:
      LOGGER.error('Config file read error: %s', self.fileName)
      self.readSuccess = False
      return False
    for kv, vv in res:                # Parse each line
      # Check key
      key = reFindall(r'^"([^"]+)"$|^([\w-]+)$', kv)
      if key == []:
        LOGGER.warning('Wrong key in line \'%s %s %s\'', kv, self.delimiter, vv)
      else:                           # Key is OK
        key = key[0][0] + key[0][1]   # Join two possible keys variants (with and without quotes)
        if vv.strip() == '':
          LOGGER.warning('No value specified in line \'%s %s %s\'', kv, self.delimiter, vv)
        else:                         # Value is not empty
          value = self.getValue(vv)   # Parse values
          if value is None:
            LOGGER.warning('Wrong value(s) in line \'%s %s %s\'', kv, self.delimiter, vv)
          else:                       # Value is OK
            if key in self.keys():    # Check double values
              LOGGER.warning('Double values for one key:\n%s = %s\nand\n%s = %s\nLast one is stored.', key, self[key], key, value)
            self[key] = value         # Store last value
            LOGGER.debug('Config value read as: %s = %s', key, str(value))
    LOGGER.info('Config read: %s', self.fileName)
    return True

  def encode(self, val):                # Convert value to string before save it
    if isinstance(val, bool):       # Treat Boolean
      val = self.boolval[0] if val else self.boolval[1]
    if self.usequotes:
      val = '"' + val + '"'         # Put value within quotes
    return val

  def save(self):
    """ save in-memory configuration to file on disk """
    try:                                  # Read the file in buffer
      with open(self.fileName, 'rt') as cf:
        buf = cf.read()
    except:
      LOGGER.warning('Config file access error, a new file (%s) will be created', self.fileName)
      buf = ''
    buf = reSub(r'[\n]*$', '\n', buf)     # Remove all ending blank lines except the one.
    for key, value in self.items():
      if value is None:
        res = ''                          # Remove 'key=value' from file if value is None
        LOGGER.debug('Config value \'%s\' will be removed', key)
      else:                               # Make a line with value
        res = self.delimiter.join([key,
                                   ', '.join(self.encode(val) for val in CVal(value))]) + '\n'
        LOGGER.debug('Config value to save: %s', res[:-1])
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
      LOGGER.error('Config file write error: %s', self.fileName)
      return False
    LOGGER.info('Config written: %s', self.fileName)
    self.changed = False                  # Reset flag of change in not stored config
    return True

def activateActions(activate):  
  """ Install/deinstall file extensions """
  # global APPINSTPATH
  userHome = getenv("HOME")
  result = False
  try:                  # Catch all exceptions during FM action activation/deactivation

    # --- Actions for Nautilus ---
    if which("nautilus") is not None:
      LOGGER.info("Nautilus installed")
      ver = check_output(["lsb_release", "-rs"])
      if ver != '' and float(ver) < 12.10:
        nautilusPath = ".gnome2/nautilus-scripts/"
      else:
        nautilusPath = ".local/share/nautilus/scripts"
      LOGGER.debug(nautilusPath)
      if activate:      # Install actions for Nautilus

        copyFile(pathJoin(APPINSTPATH, "fm-actions/Nautilus_Nemo/publish"),
                 pathJoin(userHome, nautilusPath, _("Publish via Yandex.Disk")))
        copyFile(pathJoin(APPINSTPATH, "fm-actions/Nautilus_Nemo/unpublish"),
                 pathJoin(userHome, nautilusPath, _("Unpublish from Yandex.disk")))
      else:             # Remove actions for Nautilus
        deleteFile(pathJoin(userHome, nautilusPath, _("Publish via Yandex.Disk")))
        deleteFile(pathJoin(userHome, nautilusPath, _("Unpublish from Yandex.disk")))
      result = True

    # --- Actions for Nemo ---
    if which("nemo") is not None:
      LOGGER.info("Nemo installed")
      if activate:      # Install actions for Nemo
        copyFile(pathJoin(APPINSTPATH, "fm-actions/Nautilus_Nemo/publish"),
                 pathJoin(userHome, ".local/share/nemo/scripts", _("Publish via Yandex.Disk")))
        copyFile(pathJoin(APPINSTPATH, "fm-actions/Nautilus_Nemo/unpublish"),
                 pathJoin(userHome, ".local/share/nemo/scripts", _("Unpublish from Yandex.disk")))
      else:             # Remove actions for Nemo
        deleteFile(pathJoin(userHome, ".gnome2/nemo-scripts", _("Publish via Yandex.Disk")))
        deleteFile(pathJoin(userHome, ".gnome2/nemo-scripts", _("Unpublish from Yandex.disk")))
      result = True

    # --- Actions for Thunar ---
    if which("thunar") is not None:
      LOGGER.info("Thunar installed")
      ucaPath = pathJoin(userHome, ".config/Thunar/uca.xml")
      # Read uca.xml
      with open(ucaPath) as ucaf:
        [(ust, actions, uen)] = reFindall(r'(^.*<actions>)(.*)(<\/actions>)', ucaf.read(), reS)
      acts = reFindall(r'(<action>.*?<\/action>)', actions, reS)
      nActs = {reFindall(r'<name>(.+?)<\/name>', u, reS)[0]: u for u in acts}

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
    if which("dolphin") is not None:
      LOGGER.info("Dolphin installed")
      if activate:      # Install actions for Dolphin
        makeDirs(pathJoin(userHome, '.local/share/kservices5/ServiceMenus'))
        copyFile(pathJoin(APPINSTPATH, "fm-actions/Dolphin/ydpublish.desktop"),
                 pathJoin(userHome, ".local/share/kservices5/ServiceMenus/ydpublish.desktop"))
      else:             # Remove actions for Dolphin
        deleteFile(pathJoin(userHome, ".local/share/kservices5/ServiceMenus/ydpublish.desktop"))
      result = True

    # --- Actions for Pantheon-files ---
    if which("pantheon-files") is not None:
      LOGGER.info("Pantheon-files installed")
      ctrs_path = "/usr/share/contractor/"
      if activate:      # Install actions for Pantheon-files
        src_path = pathJoin(APPINSTPATH, "fm-actions", "pantheon-files")
        ctr_pub = pathJoin(src_path, "yandex-disk-indicator-publish.contract")
        ctr_unpub = pathJoin(src_path, "yandex-disk-indicator-unpublish.contract")
        res = call(["gksudo", "-D", "yd-tools", "cp", ctr_pub, ctr_unpub, ctrs_path])
        if res == 0:
          result = True
        else:
          LOGGER.error("Cannot enable actions for Pantheon-files")
      else:             # Remove actions for Pantheon-files
        res = call(["gksudo", "-D", "yd-tools", "rm",
                    pathJoin(ctrs_path, "yandex-disk-indicator-publish.contract"),
                    pathJoin(ctrs_path, "yandex-disk-indicator-unpublish.contract")])
        if res == 0:
          result = True
        else:
          LOGGER.error("Cannot disable actions for Pantheon-files")

    # --- Actions for Caja ---
    if which("caja") is not None:
      LOGGER.info("Caja installed")
      if activate:      # Install actions for Nemo
        copyFile(pathJoin(APPINSTPATH, "fm-actions/Nautilus_Nemo/publish"),
                 pathJoin(userHome, ".config/caja/scripts", _("Publish via Yandex.Disk")))
        copyFile(pathJoin(APPINSTPATH, "fm-actions/Nautilus_Nemo/unpublish"),
                 pathJoin(userHome, ".config/caja/scripts", _("Unpublish from Yandex.disk")))
      else:             # Remove actions for Nemo
        deleteFile(pathJoin(userHome, ".config/caja/scripts", _("Publish via Yandex.Disk")))
        deleteFile(pathJoin(userHome, ".config/caja/scripts", _("Unpublish from Yandex.disk")))
      result = True

  except Exception as e:
    LOGGER.error("The following error occurred during the FM actions activation:\n %s", str(e))
  return result

def checkAutoStart(path):       
  """ Check that auto-start is enabled """
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
  """ Sets the executable name """
  from ctypes import cdll, byref, create_string_buffer
  libc = cdll.LoadLibrary('libc.so.6')
  buff = create_string_buffer(len(newname) + 1)
  buff.value = bytes(newname, 'UTF8')
  libc.prctl(15, byref(buff), 0, 0, 0)

def argParse(ver):              
  """ Parse command line arguments """
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
  group.add_argument('-v', '--version', action='version', version='%(prog)s v.' + ver,
            help=_('Print version and exit'))
  return parser.parse_args()
