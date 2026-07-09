
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
version = "0.1.10"
comm = PLC()
output_format = "raw"
output_formats = ["raw", "readable", "minimal"]
show_timing = False

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

def write(args):
    words = args.split(maxsplit=1)  # split tag from value so string values may contain spaces.
    tag, value = words[0], words[1]
    comm.Read(tag)  # Always read the tag first since this will initiate the connection.
    try:
        if isInteger(value):
            ret = comm.Write(tag, int(value))
        else:
            ret = comm.Write(tag, value)
    except Exception as e:
        print("ERROR - Could not write value '{0}' to tag '{1}'.  "
              "The value type may not match the tag's datatype.  ({2})".format(value, tag, e))
        return
    print(ret)

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
    if (args in output_formats):
        output_format = args
        print("Output format set to {}".format(args))
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
        Version                     - Returns the version of pylogix_cli and pylogix.
        GetTagList                  - Returns the list of tags in the target PLC.
        GetProgramsList             - Returns the list of programs.
        Output (Raw | Readable)     - Sets the output format.  Raw is the default.        
    
    Multi-Tag Commands: (Filenames are case sensitive.)
        ReadTagFile <filename> [<outfile>]
            - Returns the values of the tags from the file.
          
    ''')

#endregion CONSOLE COMMAND DEFINITIONS

#region COMMAND LOOP
def parseCommand(command):
    words = command.casefold().split()
    if (len(words) > 0):
        if (words[0] == "help"):
            getHelp(command)
        elif (words[0] == "ipaddress"):
            ipAddress(getAdditionalArgs(command))
        elif (words[0] == "getplctime"):
            getPLCTime(getAdditionalArgs(command))
        elif (words[0] == "setplctime"):
            setPLCTime(getAdditionalArgs(command))
        elif (words[0] == "setplcgateway"):
            setPLCGateway(getAdditionalArgs(command))
        elif (words[0] == "getdeviceproperties"):
            getDeviceProperties(getAdditionalArgs(command))
        elif (words[0] == "getmoduleproperties"):
            getModuleProperties(getAdditionalArgs(command))
        elif (words[0] == "getfaultcodes"):
            getFaultCodes(getAdditionalArgs(command))
        elif (words[0] == "getfaultinfo"):
            getFaultInfo(getAdditionalArgs(command))
        elif (words[0] == "read"):
            read(getAdditionalArgs(command))
        elif (words[0] == "readtagfile"):
            readTagFile(getAdditionalArgs(command))
        elif (words[0] == "write"):
            write(getAdditionalArgs(command))
        elif (words[0] == "version"):
            getVersion(getAdditionalArgs(command))
        elif (words[0] == "gettaglist"):
            getTagList(getAdditionalArgs(command))
        elif (words[0] == "getprogramslist"):
            getProgramsList(getAdditionalArgs(command))
        elif (words[0] == "output"):
            output(getAdditionalArgs(command))
        else:
            print("ERROR - Unrecognized command.  Enter Help for a list of commands.")

def commandLoop():
    command = input("pylogix_cli> ").casefold()
    while (command != "quit" and command != "exit"):
        parseCommand(command)
        command = input("pylogix_cli> ").casefold()
    if command == "exit":
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
    words = command.casefold().split()
    if (len(words) > 1):
        return " ".join(words[1:])
    else:
        return ""
    
def getTagValues(tags):
    outData = []
    for tag in tags:
        if len(tag) > 0:
            try:
                result = comm.Read(tag).Value
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
        commandLoop()
    comm.Close()

#endregion MAIN

main()
