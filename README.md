# pylogix_cli

The pylogix_cli application is intended to encapsulate all of the pylogix commands into a single directly executable program.  Using pyinstaller, pylogix_cli can be packaged into an .exe file that can be run on any Windows computer without the need for installing Python.  This can be particularly
handy for systems where an end-user does not have the Rockwell software, but needs to update a value, set the time on the controller or read or write settings from or to the target PLC.

Warning!  PLCs control industrial equipment and writing values to a PLC that is actively operating equipment should be done with great care and is at your own risk.

Click below to download the current standalone executable for Windows 7/10:<br/>
https://github.com/dhunt84971/pylogix_cli/releases/download/v0.1.10/pylogix_cli.exe 


Execution of the application will take the form of a single command or a shell console application allowing multiple commands to be executed.

## Examples of Usage
Single command syntax example:
```
pylogix_cli 192.168.1.10 Read CurrentScreen
None 12 Success
```
![Peek 2022-04-18 15-17](https://user-images.githubusercontent.com/674065/163863258-3edac336-dc3b-4469-b1a2-660256805834.gif)

### Specifying the Controller Slot
In a chassis-based platform (such as a ControlLogix rack), the processor may
reside in any slot.  The slot number tells pylogix_cli where in the chassis to
find the controller.  When no slot is specified, slot 0 is assumed, which
matches the original behavior and covers the common case (including CompactLogix
and other single-slot controllers).

To target a controller in a different slot, append the slot number to the IP
address after a comma:
```
pylogix_cli 192.168.1.10,2 Read CurrentScreen
None 12 Success
```
The same comma-separated syntax works with the `IPAddress` console command:
```
pylogix_cli> IPAddress 192.168.1.10,2
```


Console app example:
```
pylogix_cli 192.168.1.10
pylogix_cli> Read CurrentScreen
None 12 Success
pylogix_cli> quit
```

OR
```
pylogix_cli
pylogix_cli> Read CurrentScreen
ERROR - No IPAddress specified.  Use IPAddress command.
pylogix_cli> IPAddress 192.168.1.10
pylogix_cli> Read CurrentScreen
None 12 Success
pylogix_cli> quit
```
![Peek 2022-04-18 15-13](https://user-images.githubusercontent.com/674065/163862795-0810d192-76c8-40b5-a798-819640d2ef5f.gif)



## The pylogix Project
This application is a command line wrapper to ease the use of the many functions of the pylogix library.  The pyinstaller program is used to create an executable package on Windows that does not require the installation of Python.

For more information and documentation:
https://github.com/dmroeder/pylogix

**Special thanks to dmroeder and all the contributors that make pylogix possible.**

## Currently Implemented Functions
```
        Help                        - Displays this list of commands.
        IPAddress <ip address>[,<slot>]
                                    - Sets the IP address (and optional slot) for the target PLC.
        Quit                        - Leave console application.
        GetPLCTime                  - Returns the PLC time.
        SetPLCTime                  - Sets the PLC time and time zone to match this computer.
        SetPLCGateway <ip address>  - Sets the PLC's default gateway address.
        GetModuleProperties <slot>  - Gets the properties of the module in the specified slot.
        GetDeviceProperties         - Gets the properties of the connected device.
        * GetFaultCodes             - Gets the Type and Code of the current controller fault.
        * GetFaultInfo              - Gets the Module slot for an IO fault or location for a logic fault.
        Read <tag>                  - Returns the specified tag's value from the target PLC.
        Write <tag> <value>         - Sets the specified tag's value in the target PLC.
        Version                     - Returns the version of pylogix_cli and pylogix.
        GetTagList                  - Returns the list of tags in the target PLC.
        Output (Raw | Readable)     - Sets the output format.  Raw is the default.     

* - Is not a standard pylogix command.
```
(Commands are not case sensitive.)

### Multi-Tag Commands:
Filenames are case sensitive.
+ ```ReadTagFile <filename> [<outfile>]```
    - Returns the values of the tags from the file.

## Development Environment
A copy of the pylogix library is vendored in this repository (in the `pylogix/`
folder) so the executable is self-contained and includes local modifications
(such as SetPLCTime setting the controller time zone).  Because pylogix is
bundled, only pyinstaller needs to be installed to build the executable.

```
git clone https://github.com/dhunt84971/pylogix_cli.git
cd pylogix_cli
pip install pyinstaller
```

### Building the Executable
In order to build the executable for the Windows platform it is necessary to run pyinstaller on a Windows computer.  Keep in mind that Python 3.9+ cannot run on Windows 7.  For this reason it is recommended that a Windows 7 system with Python installed be used to create the executable in order to ensure compatability with Windows 7 and newer versions of Windows.
 
```
pyinstaller -F pylogix_cli.py
```

## License

This project is licensed under Apache 2.0 License - see the [LICENSE](LICENSE.txt) file for details.

