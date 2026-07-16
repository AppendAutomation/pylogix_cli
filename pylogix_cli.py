
'''
The pylogix_cli application is intended to encaspulate all of the pylogix 
commands into a single directly executable program.  Using pyinstaller,
pylogix_cli can be packaged into an .exe file that can be run on any Windows
computer without the need for installing Python.  This can be particularly
handy for systems where an end-user does not have the Rockwell software, but
needs to update a value, set the time on the controller or read or write
settings from or to the target PLC.

Execution of the application will take the form of a single command or a shell
console application allowing multiple commands to be executed.

Single command syntax:
pylogix_cli 192.168.1.10 Read CurrentScreen

An optional processor slot number may be appended to the IP address after a
comma (defaults to slot 0 when omitted):
pylogix_cli 192.168.1.10,2 Read CurrentScreen

Console app example:
pylogix_cli 192.168.1.10
> Read CurrentScreen
12
> quit

- or -

pylogix_cli
> Read CurrentScreen
ERROR - No IPAdress specified.  Use IPAddress command.
> IPAddress 192.168.1.10
> Read CurrentScreen
12
> quit

'''

'''
the following import is only necessary because eip.py is not in this directory
'''
import sys
import os
import datetime
import time

from pathlib import Path
from struct import pack, unpack, unpack_from

# Prefer the pylogix package vendored alongside this script (it contains
# local modifications, e.g. SetPLCTime time zone support) over any version
# that may be installed system-wide.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pylogix
from pylogix.lgx_response import Response
from pylogix import PLC
version = "0.2.0"
comm = PLC()
output_format = "raw"
output_formats = ["raw", "readable", "minimal"]
show_timing = False
# Set True by the Wait command when the user presses 'c' to cancel a running
# script.  RunScript checks and clears it after each command.
cancel_requested = False

#region CUSTOM COMMAND CODE
def get_cip_attribute(plc, class_inst_id, attribute_id, instance_id, offset = 54):
    """
    Requests the cip attribute given the class, attribute and instance.
    """
    conn = plc.conn.connect(False)
    if not conn[0]:
        return Response(None, None, conn[1])

    # Future for when classes > 255 are implemented.
    # cip_size=0x00

    # if class_inst_id <= 255:
    #     cip_size = cip_size + 1
    #     cip_class_type = 0x20
    #     cip_class_pack_format = 'BB'
    # else:
    #     cip_size = cip_size + 2
    #     cip_class_type = 0x21
    #     cip_class_pack_format = 'HH'

    # if instance_id <= 255:
    #     cip_size = cip_size + 1
    #     cip_instance_type = 0x24
    #     cip_inst_pack_format = 'BB'
    # else:
    #     cip_size = cip_size + 2
    #     cip_instance_type = 0x25
    #     cip_inst_pack_format = 'HH'
        
    if instance_id <= 255:
        cip_size = 0x02
        cip_instance_type = 0x24
        pack_format = '<BBBBBBH1H'
    else:
        cip_size = 0x03
        cip_instance_type = 0x25
        pack_format = '<BBBBHHHH'

    cip_service = 0x03
    cip_class_type = 0x20
    cip_class = class_inst_id
    cip_instance = instance_id
    cip_count = 0x01
    cip_attribute = attribute_id

    request = pack(pack_format,
                    cip_service,
                    cip_size,
                    cip_class_type,
                    cip_class,
                    cip_instance_type,
                    cip_instance,
                    cip_count,
                    cip_attribute)
    
    status, ret_data = plc.conn.send(request, False)
    if status == 0:
        value = ret_data[offset:]
    else:
        value = None
    return Response(None, value, status)



"""
Credit to dmroeder. https://github.com/dmroeder
"""
def get_controller_fault(plc):
    """
    User configurable CIP command.  It is up to you to understand the
    data that will be returned
    
    returns Response class (.TagName, .Value, .Status
    """
    conn = plc.conn.connect(True)
    if not conn[0]:
        return Response(None, None, conn[1])

    cip_service = 0x01
    cip_service_size = 0x02
    cip_class_type = 0x20
    cip_class = 0x73
    cip_instance_type = 0x24
    cip_instance = 0x01

    request = pack('<BBBBBB',
                    cip_service,
                    cip_service_size,
                    cip_class_type,
                    cip_class,
                    cip_instance_type,
                    cip_instance)

    status, ret_data = plc.conn.send(request, False)
    value = {"type":None, "code":None, "id1":None, "id2":None, "id3":None, "data":None}

    if status == 0:
        data = ret_data[44:]
        value["type"] = unpack_from("<H", data, 20)[0]
        value["code"] = unpack_from("<H", data, 22)[0]
        value["id1"] = unpack_from("<H", data, 24)[0]
        value["id2"] = unpack_from("<H", data, 28)[0]
        value["id3"] = unpack_from("<H", data, 32)[0]
        value["data"] = unpack_from("<H", data, 36)[0]

    return Response(None, value, status)

def get_task_name(plc, instance):
    response = get_cip_attribute(plc, 112, 24, instance)
    value = response.Value.decode()
    response = Response(None, value, response.Status)
    return response

def get_program_name(plc, instance):
    response = get_cip_attribute(plc, 104, 28, instance)
    value = response.Value.decode()
    response = Response(None, value, response.Status)
    return response

def get_module_slot(plc, instance):
    response = get_cip_attribute(plc, 105, 10, instance, 50)
    value = unpack('<I', response.Value)[0]
    response = Response(None, value, response.Status)
    return response

def get_controller_fault_info(plc):
    fault_codes = get_controller_fault(plc)
    if fault_codes.Value["type"] == 0:
        value = {"failure_type": "No Fault"}
    elif fault_codes.Value["type"] == 3 and fault_codes.Value["code"] == 23:
        value = {"failure_type": "IO Module Failure on Startup"}
    # If fault is IO related, id3 = 34 else assume program fault.
    elif fault_codes.Value["id3"] == 34:
        slot = get_module_slot(plc, fault_codes.Value["id2"]).Value
        value = {"failure_type": "Required IO Module Failed", "slot":slot}
    else:
        task = get_task_name(plc, fault_codes.Value["id1"]).Value
        program = get_program_name(plc, fault_codes.Value["id2"]).Value
        value = {"failure_type": "Logic", "task":task, "program":program}

    return Response(None, value, fault_codes.Status)

#endregion CUSTOM COMMAND CODE

#region CONSOLE COMMAND DEFINITIONS
def ipAddress(args):
    ip, slot = parseIPAndSlot(args)
    comm.Close()
    comm.IPAddress = ip
    if slot is not None:
        comm.ProcessorSlot = slot

def getPLCTime(args):
    ret = comm.GetPLCTime()
    print(ret)

def setPLCTime(args):
    # always set the controller's time zone to match this computer
    ret = comm.SetPLCTime(set_timezone=True)
    print(ret)

def setPLCGateway(args):
    gateway = args.strip()
    if not isIPAddress(gateway):
        print("ERROR - Invalid argument.  Please specify a gateway address, e.g. 192.168.1.1.")
        return
    ret = comm.SetPLCGateway(gateway)
    print(ret)

def getDeviceProperties(args):
    ret = comm.GetDeviceProperties()
    print(ret)

def getModuleProperties(args):
    if not args.isnumeric():
        print("ERROR - Invalid argument.  Please specify a slot number.")
        return
    ret = comm.GetModuleProperties(int(args))
    print(ret)

def getFaultCodes(args):
    ret = get_controller_fault(comm)
    if (output_format == "raw"):
        print(ret)
    elif (output_format == "readable"):
        print("Fault Type({}), Code({})".format(ret.Value[0], ret.Value[1]))
    else:
        print(ret)

def getFaultInfo(args):
    ret = get_controller_fault_info(comm)
    if (output_format == "raw"):
        print(ret)
    else:
        print(ret)

def read(args):
    ret = comm.Read(args)
    decoded = decodeStringValue(ret.Value)
    if decoded is not None:
        ret.Value = decoded
    # surround string values in single quotes so their boundaries are clear
    # when the value contains spaces, e.g. MyStringTag 'Hello World' Success
    if isinstance(ret.Value, str):
        ret.Value = "'{}'".format(ret.Value)
    print(ret)

def readTagFile(args):
    if (comm == None):
        print("ERROR - No IPAddress specified.  Use IPAddress command.")
        return
    words = args.split()
    filename = words[0]
    start_time = time.time()
    outData = getTagValuesFromFile(filename)
    if len(outData) > 0:
        outFile = ""
        if len(words) > 1:
            outFile = words[1]
        exec_time = time.time() - start_time
        if len(outFile) > 0:
            Path(outFile).write_text("\n".join(outData))
        else:
            print("\n".join(outData))
        if (show_timing):
            print("Executed in {0:7.3f} seconds.".format(exec_time))

def writeTagValue(tag, value):
    """
    Writes a single value to a tag.  Integer-looking values are written as
    ints; everything else is passed through as-is.  pylogix coerces the value
    to the tag's actual datatype (e.g. float() for REAL tags), so a numeric
    string still writes correctly to a REAL tag.  The tag is read first because
    that initiates the connection and populates the tag's datatype.  Raises on
    failure so callers can report the error.
    """
    comm.Read(tag)  # Always read the tag first since this will initiate the connection.
    if isInteger(value):
        return comm.Write(tag, int(value))
    return comm.Write(tag, value)

def write(args):
    words = args.split(maxsplit=1)  # split tag from value so string values may contain spaces.
    tag, value = words[0], words[1]
    try:
        ret = writeTagValue(tag, value)
    except Exception as e:
        print("ERROR - Could not write value '{0}' to tag '{1}'.  "
              "The value type may not match the tag's datatype.  ({2})".format(value, tag, e))
        return
    print(ret)

def writeTagFile(args):
    """
    Writes the tag/value pairs contained in a comma delimited file.  Each line
    is "tag, value"; blank lines and lines beginning with '#' are ignored so
    the file may be commented.  Every value is written to its tag and the
    result of each write is printed.
    """
    words = args.split()
    if len(words) == 0:
        print("ERROR - Please specify a filename.")
        return
    filename = words[0]
    try:
        lines = Path(filename).read_text().splitlines()
    except Exception as error:
        print("ERROR - Error opening the file {0}. {1}".format(filename, str(error)))
        return
    start_time = time.time()
    for lineNum, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        if "," not in stripped:
            print("Line {0}: ERROR - Expected 'tag, value'.  Skipping '{1}'.".format(lineNum, stripped))
            continue
        tag, value = stripped.split(",", 1)
        tag = tag.strip()
        value = value.strip()
        try:
            print(writeTagValue(tag, value))
        except Exception as e:
            print("ERROR - Could not write value '{0}' to tag '{1}'.  "
                  "The value type may not match the tag's datatype.  ({2})".format(value, tag, e))
    if (show_timing):
        print("Executed in {0:7.3f} seconds.".format(time.time() - start_time))

def sleep(args):
    """
    Pauses execution for the given number of seconds.  Useful in script files
    to allow the PLC time to react between commands.  Fractional seconds are
    allowed, e.g. "Sleep 0.5".
    """
    val = args.strip()
    try:
        seconds = float(val)
    except ValueError:
        print("ERROR - Invalid argument.  Please specify the number of seconds to sleep.")
        return
    if seconds < 0:
        print("ERROR - The number of seconds to sleep must not be negative.")
        return
    time.sleep(seconds)

WAIT_CONDITIONALS = (">", "<", ">=", "<=", "==", "!=")

def wait(args):
    """
    Repeatedly reads a tag until it satisfies a condition, then returns.

        wait <tag> <conditional> <value> [echo=y] [interval=1] [timeout=<seconds>]

    conditional is one of >, <, >=, <=, ==, !=.  The optional arguments may be
    given in any order:
        echo=y|n     - echo each read to the terminal (default y)
        interval=<s> - seconds between reads (default 1)
        timeout=<s>  - give up after this many seconds (default: no timeout).
                       A bare number is also accepted as the timeout.

    While waiting the user may press 'q' to stop waiting (and continue) or 'c'
    to cancel a running script.
    """
    global cancel_requested
    words = args.split()
    if len(words) < 3:
        print("ERROR - Usage: wait <tag> <conditional> <value> "
              "[echo=y] [interval=1] [timeout=<seconds>]")
        return
    tag, conditional, target = words[0], words[1], words[2]
    if conditional not in WAIT_CONDITIONALS:
        print("ERROR - Invalid conditional '{0}'.  Use one of {1}.".format(
            conditional, ", ".join(WAIT_CONDITIONALS)))
        return

    # defaults for the optional arguments
    echo = True
    interval = 1.0
    timeout = None
    for opt in words[3:]:
        key, sep, val = opt.partition("=")
        key = key.casefold()
        if not sep:
            # a bare token is treated as the timeout, per "[timeout]"
            try:
                timeout = float(opt)
            except ValueError:
                print("ERROR - Unrecognized option '{0}'.".format(opt))
                return
            continue
        if key == "echo":
            echo = val.strip().casefold() in ("y", "yes", "true", "1", "on")
        elif key == "interval":
            try:
                interval = float(val)
            except ValueError:
                print("ERROR - Invalid interval '{0}'.".format(val))
                return
        elif key == "timeout":
            try:
                timeout = float(val)
            except ValueError:
                print("ERROR - Invalid timeout '{0}'.".format(val))
                return
        else:
            print("ERROR - Unrecognized option '{0}'.".format(opt))
            return

    if interval < 0:
        print("ERROR - The interval must not be negative.")
        return

    if sys.stdin.isatty():
        print("Waiting for {0} {1} {2} ... (press 'q' to skip, 'c' to cancel script)".format(
            tag, conditional, target), flush=True)

    start_time = time.time()
    old_term = enterCbreak()
    try:
        while True:
            ret = comm.Read(tag)
            current = ret.Value
            decoded = decodeStringValue(current)
            if decoded is not None:
                current = decoded
                ret.Value = decoded
            if echo:
                # flush so echoed reads appear in real time even when output is
                # redirected to a file or pipe during a long wait.
                print(ret, flush=True)

            if current is not None:
                current_cmp, target_cmp = coerceForCompare(current, target)
                if evalConditional(current_cmp, conditional, target_cmp):
                    print("Condition met: {0} {1} {2} (current {3}).".format(
                        tag, conditional, target, current), flush=True)
                    return

            if timeout is not None and (time.time() - start_time) >= timeout:
                print("Wait timed out after {0:g} seconds; condition {1} {2} {3} not met.".format(
                    timeout, tag, conditional, target), flush=True)
                return

            key = sleepWithKey(interval)
            if key == "q":
                print("Wait stopped by user.", flush=True)
                return
            elif key == "c":
                print("Script cancelled by user.", flush=True)
                cancel_requested = True
                return
    finally:
        exitCbreak(old_term)

def validateScriptLines(lines):
    """
    Checks that every non-blank, non-comment line in a script begins with a
    recognized command.  Returns a list of human readable error strings; an
    empty list means the script is valid.
    """
    errors = []
    for lineNum, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        word = stripped.split()[0]
        cmd = word.casefold()
        # quit/exit are handled by the command loop, not parseCommand, but are
        # valid inside a script where they simply stop execution.
        if cmd in ("quit", "exit"):
            continue
        if cmd not in COMMANDS:
            errors.append("Line {0}: Unrecognized command '{1}'.".format(lineNum, word))
    return errors

def readScriptLines(filename):
    """
    Reads a script file and returns its lines, or None if the file could not
    be opened (an error is printed in that case).
    """
    try:
        return Path(filename).read_text().splitlines()
    except Exception as error:
        print("ERROR - Error opening the file {0}. {1}".format(filename, str(error)))
        return None

def validateScript(args):
    """
    Validates a script file without executing it, reporting any lines that do
    not begin with a recognized command.
    """
    words = args.split()
    if len(words) == 0:
        print("ERROR - Please specify a script filename.")
        return
    filename = words[0]
    lines = readScriptLines(filename)
    if lines is None:
        return
    errors = validateScriptLines(lines)
    if errors:
        print("Script {0} is INVALID:".format(filename))
        for err in errors:
            print("  " + err)
    else:
        print("Script {0} is valid.".format(filename))

def runScript(args):
    """
    Validates and then executes a script file.  Each line is a command exactly
    as it would be typed in the interactive console.  Blank lines and lines
    beginning with '#' are ignored so scripts may be commented.  The script is
    validated first and is not executed at all if any command is unrecognized.
    A quit/exit line stops the script early, as does the user pressing 'c'
    during a Wait command.
    """
    global cancel_requested
    words = args.split()
    if len(words) == 0:
        print("ERROR - Please specify a script filename.")
        return
    filename = words[0]
    lines = readScriptLines(filename)
    if lines is None:
        return
    errors = validateScriptLines(lines)
    if errors:
        print("ERROR - Script validation failed for {0}:".format(filename))
        for err in errors:
            print("  " + err)
        print("Script not executed.")
        return
    cancel_requested = False
    start_time = time.time()
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        if stripped.casefold() in ("quit", "exit"):
            break
        # echo the command so the script's progress is visible
        print("pylogix_cli> " + stripped)
        parseCommand(stripped)
        if cancel_requested:
            print("Script {0} cancelled.".format(filename))
            cancel_requested = False
            break
    if (show_timing):
        print("Script {0} executed in {1:7.3f} seconds.".format(filename, time.time() - start_time))

def getVersion(args):
    print("pylogix_cli v" + version + ", pylogix v" + pylogix.__version__)

def getTagList(args):
    tags = comm.GetTagList()
    for tag in tags.Value:
        print(tag.TagName, tag.DataType)

def getProgramsList(args):
    programs = comm.GetProgramsList()
    for program in programs.Value:
        print(program)

def validateTags(args):
    fileName = args
    with open(fileName, encoding="utf-8") as f:
        for line in f:
            ret = comm.Read(line)
            print(ret)

def output(args):
    global output_format
    fmt = args.casefold()
    if (fmt in output_formats):
        output_format = fmt
        print("Output format set to {}".format(fmt))
    else:
        print("Invalid output format")
    return

def getHelp(args):
    print('''
    Commands: (Not case sensitive.)
        Help                        - Displays this list of commands.
        IPAddress <ip address>[,<slot>]
                                    - Sets the IP address (and optional slot) for the target PLC.
        Quit                        - Leave console application.
        GetPLCTime                  - Returns the PLC time.
        SetPLCTime                  - Sets the PLC time and time zone to match this computer.
        SetPLCGateway <ip address>  - Sets the PLC's default gateway address.
        GetModuleProperties <slot>  - Gets the properties of the module in the specified slot.
        GetDeviceProperties         - Gets the properties of the connected device.
        GetFaultCodes               - Gets the Type and Code of the current controller fault.
        GetFaultInfo                - Gets the Module slot for an IO fault or location for a logic fault.
        Read <tag>                  - Returns the specified tag's value from the target PLC.
        Write <tag> <value>         - Sets the specified tag's value in the target PLC.
        Sleep <seconds>             - Pauses execution for the given number of seconds.
        Wait <tag> <cond> <value> [echo=y] [interval=1] [timeout=<seconds>]
                                    - Reads <tag> until it <cond> <value>, where <cond> is
                                      one of >, <, >=, <=, ==, !=.  Press 'q' to skip the
                                      wait or 'c' to cancel a running script.
        Version                     - Returns the version of pylogix_cli and pylogix.
        GetTagList                  - Returns the list of tags in the target PLC.
        GetProgramsList             - Returns the list of programs.
        Output (Raw | Readable)     - Sets the output format.  Raw is the default.

    Multi-Tag Commands: (Filenames are case sensitive.)
        ReadTagFile <filename> [<outfile>]
            - Returns the values of the tags from the file.
        WriteTagFile <filename>
            - Writes the comma delimited "tag, value" pairs from the file.

    Script Commands: (Filenames are case sensitive.)
        RunScript <filename>
            - Validates then executes a file of console commands, one per line.
        ValidateScript <filename>
            - Checks a script file for unrecognized commands without executing it.

    ''')

#endregion CONSOLE COMMAND DEFINITIONS

#region COMMAND LOOP
# Maps a (case-insensitive) command word to its handler.  Every handler takes
# a single argument: the text that follows the command word.  This table is
# used both to dispatch commands and to validate script files.
COMMANDS = {
    "help": getHelp,
    "ipaddress": ipAddress,
    "getplctime": getPLCTime,
    "setplctime": setPLCTime,
    "setplcgateway": setPLCGateway,
    "getdeviceproperties": getDeviceProperties,
    "getmoduleproperties": getModuleProperties,
    "getfaultcodes": getFaultCodes,
    "getfaultinfo": getFaultInfo,
    "read": read,
    "readtagfile": readTagFile,
    "write": write,
    "writetagfile": writeTagFile,
    "sleep": sleep,
    "wait": wait,
    "runscript": runScript,
    "validatescript": validateScript,
    "version": getVersion,
    "gettaglist": getTagList,
    "getprogramslist": getProgramsList,
    "output": output,
}

def parseCommand(command):
    words = command.split()
    if (len(words) > 0):
        handler = COMMANDS.get(words[0].casefold())
        if handler is not None:
            handler(getAdditionalArgs(command))
        else:
            print("ERROR - Unrecognized command.  Enter Help for a list of commands.")

def commandLoop():
    # Keep the raw input so argument case is preserved (e.g. string values
    # written to tags).  Command matching is done case-insensitively below.
    command = input("pylogix_cli> ").strip()
    while (command.casefold() != "quit" and command.casefold() != "exit"):
        parseCommand(command)
        command = input("pylogix_cli> ").strip()
    if command.casefold() == "exit":
        print("I'll assume you meant quit.")

#endregion COMMAND LOOP

#region HELPER FUNCTIONS
def isIPAddress(value):
    ip, _ = parseIPAndSlot(value)
    return len(ip.split(".")) == 4

def parseIPAndSlot(value):
    """
    Splits a target specifier into an IP address and an optional slot number.
    The slot may be appended to the IP address after a comma, e.g.
    "192.168.1.10,2".  When no slot is given the slot is returned as None so
    the caller can leave the pylogix default (slot 0) untouched.
    """
    parts = value.split(",", 1)
    ip = parts[0].strip()
    slot = None
    if len(parts) > 1:
        slotStr = parts[1].strip()
        if slotStr.isdigit():
            slot = int(slotStr)
    return ip, slot

def getAdditionalArgs(command):
    # Return everything after the command word verbatim so argument case
    # and internal spacing are preserved (needed for string tag values).
    parts = command.split(maxsplit=1)
    if (len(parts) > 1):
        return parts[1]
    else:
        return ""
    
def decodeStringValue(value):
    """
    Custom string types (e.g. STRING_20, STRING_40) come back from pylogix as
    raw structure bytes: a 4 byte length (LEN) followed by the character data
    (DATA) padded with nulls.  Decode that into a plain string so it displays
    cleanly instead of showing the length prefix, null padding and b'...'
    quotes.  Returns None when the bytes don't look like a Logix string so the
    caller can fall back to the raw value (e.g. a genuine UDT).
    """
    if not isinstance(value, (bytes, bytearray)):
        return None
    if len(value) < 4:
        return None
    length = int.from_bytes(value[0:4], "little")
    if length > len(value) - 4:
        return None
    try:
        text = value[4:4 + length].decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return None
    # only treat it as a string if the characters are printable text
    if any(ord(c) < 0x20 and c not in "\t\r\n" for c in text):
        return None
    return text

def getTagValues(tags):
    outData = []
    for tag in tags:
        if len(tag) > 0:
            try:
                result = comm.Read(tag).Value
                decoded = decodeStringValue(result)
                if decoded is not None:
                    result = decoded
                if str(result) == "None":
                    result = "!ERROR!"
            except Exception as error:
                #print("Error reading: " + tag + " - " + str(error))
                outData += [tag + "=!ERROR!"]
                continue
            outData += [tag + "=" + str(result)]
    return outData

def getTagValuesFromFile(filename):
    tags = []
    try:
        tags = Path(filename).read_text().split("\n")
    except Exception as error:
        print("ERROR - Error opening the file {0}. {1}".format(filename, str(error)))
        return []
    outData = getTagValues(tags)
    return outData

def isInteger(s):
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()

def coerceForCompare(current, target):
    """
    Returns (current, target) coerced to comparable types so a value read from
    the PLC can be compared against the string target given on the command
    line.  Booleans are compared as booleans, numbers as floats, and anything
    else as strings.  Note bool must be checked before int because in Python a
    bool is an int.
    """
    if isinstance(current, bool):
        truthy = target.strip().casefold() in ("1", "true", "y", "yes", "on")
        return current, truthy
    if isinstance(current, (int, float)):
        try:
            return current, float(target)
        except (ValueError, TypeError):
            return str(current), target
    return str(current), target

def evalConditional(current, conditional, target):
    """
    Evaluates "current <conditional> target" for the supported operators.
    Returns False (rather than raising) when the two values can't be compared.
    """
    try:
        if conditional == ">":
            return current > target
        elif conditional == "<":
            return current < target
        elif conditional == ">=":
            return current >= target
        elif conditional == "<=":
            return current <= target
        elif conditional == "==":
            return current == target
        elif conditional == "!=":
            return current != target
    except TypeError:
        return False
    return False

def getKeyNonBlocking():
    """
    Returns a single character if a key is waiting on stdin, else None.  Works
    on Windows (msvcrt) and Unix (select), and returns None when stdin is not
    an interactive terminal (e.g. commands piped in from a file) so it never
    blocks.  Unix callers must first put the terminal in cbreak mode (see
    enterCbreak) so single keys are delivered without waiting for Enter.
    """
    try:
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getch().decode(errors="ignore")
            return None
        if not sys.stdin.isatty():
            return None
        import select
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            return sys.stdin.read(1)
        return None
    except Exception:
        return None

def enterCbreak():
    """
    Puts the Unix terminal into cbreak mode so getKeyNonBlocking can read one
    key at a time without the user pressing Enter.  Returns the previous
    terminal settings (to be passed to exitCbreak) or None when nothing was
    changed (Windows, or stdin is not a terminal).
    """
    if os.name == "nt" or not sys.stdin.isatty():
        return None
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return old
    except Exception:
        return None

def exitCbreak(old):
    """Restores the terminal settings saved by enterCbreak."""
    if old is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)
    except Exception:
        pass

def sleepWithKey(seconds):
    """
    Sleeps up to `seconds`, returning early with the (lower-cased) key the user
    pressed, or None if the full time elapsed with no key.  Polls in small
    slices so a keypress is noticed promptly.
    """
    end = time.time() + seconds
    while True:
        key = getKeyNonBlocking()
        if key:
            return key.lower()
        remaining = end - time.time()
        if remaining <= 0:
            return None
        time.sleep(min(0.05, remaining))

#endregion HELPER FUNCTIONS

#region MAIN
def main():
    arguments = sys.argv
    if (len(arguments) > 1):
        if (isIPAddress(arguments[1])):
            ip, slot = parseIPAndSlot(arguments[1])
            comm.IPAddress = ip
            if slot is not None:
                comm.ProcessorSlot = slot
            if (len(arguments) > 2):
                parseCommand(" ".join(arguments[2:]))
            else:
                commandLoop()
        else:
            # The first argument isn't an IP address, so treat the arguments as
            # a command.  This lets a self-contained script that sets its own
            # IPAddress be run directly, e.g.
            #     pylogix_cli RunScript examples/test_script.txt
            parseCommand(" ".join(arguments[1:]))
    else:
        commandLoop()
    comm.Close()

#endregion MAIN

main()
