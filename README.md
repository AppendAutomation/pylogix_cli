# pylogix_cli

The pylogix_cli application is intended to encapsulate all of the pylogix commands into a single directly executable program.  Using pyinstaller, pylogix_cli can be packaged into an .exe file that can be run on any Windows computer without the need for installing Python.  This can be particularly
handy for systems where an end-user does not have the Rockwell software, but needs to update a value, set the time on the controller or read or write settings from or to the target PLC.

Warning!  PLCs control industrial equipment and writing values to a PLC that is actively operating equipment should be done with great care and is at your own risk.

Click below to download the current standalone executable for Windows 7/10:<br/>
https://github.com/dhunt84971/pylogix_cli/releases/download/v0.2.0/pylogix_cli.exe 


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

## Currently Implemented Functions and Commands
```
    pylogix Functions:
        GetDeviceProperties         - Gets the properties of the connected device.
        GetModuleProperties <slot>  - Gets the properties of the module in the specified slot.
        GetPLCTime                  - Returns the PLC time.
        GetProgramsList             - Returns the list of programs.
        GetTagList                  - Returns the list of tags in the target PLC.
        Read <tag>                  - Returns the specified tag's value from the target PLC.
        SetPLCGateway <ip address>  - Sets the PLC's default gateway address.
        SetPLCTime                  - Sets the PLC time and time zone to match this computer.
        Write <tag> <value>         - Sets the specified tag's value in the target PLC.

    pylogix_cli Functions and Commands: (Not standard pylogix commands.)
        GetFaultCodes               - Gets the Type and Code of the current controller fault.
        GetFaultInfo                - Gets the Module slot for an IO fault or location for a logic fault.
        Help                        - Displays this list of commands.
        IPAddress <ip address>[,<slot>]
                                    - Sets the IP address (and optional slot) for the target PLC.
        Output (Raw | Readable)     - Sets the output format.  Raw is the default.
        Quit                        - Leave console application.
        ReadTagFile <filename> [<outfile>]
                                    - Returns the values of the tags listed in the file.
        RunScript <filename>        - Validates and executes a file of console commands.
        Sleep <seconds>             - Pauses execution for the given number of seconds.
        ValidateScript <filename>   - Checks a script file for unrecognized commands.
        Version                     - Returns the version of pylogix_cli and pylogix.
        Wait <tag> <cond> <value> [echo=y] [interval=1] [timeout=<seconds>]
                                    - Reads <tag> until it satisfies the condition.
        WriteTagFile <filename>     - Writes the comma delimited "tag, value" pairs from the file.
```
(Commands are not case sensitive.)

More detail on the multi-tag, wait and script commands is provided in the
sections below.

### Multi-Tag Commands:
Filenames are case sensitive.
+ ```ReadTagFile <filename> [<outfile>]```
    - Returns the values of the tags from the file.  The file lists one tag
      per line.
+ ```WriteTagFile <filename>```
    - Writes the comma delimited `tag, value` pairs from the file, one pair
      per line.  Blank lines and lines starting with `#` are ignored, so the
      file may be commented.  For example:
      ```
      # zero out the setpoints
      Numbers[5], 55
      Bits.1, 1
      ```

### Waiting on a Condition:
The `Wait` command polls a tag until it satisfies a condition, then returns.
This is handy in scripts for holding until the PLC reaches a state before
continuing.
```
Wait <tag> <conditional> <value> [echo=y] [interval=1] [timeout=<seconds>]
```
+ `tag` - the tag to read and test.
+ `conditional` - one of `>`, `<`, `>=`, `<=`, `==`, `!=`.
+ `value` - the value the tag is compared against.

The optional arguments may appear in any order:
+ `echo=y|n` - echo each read to the terminal (default `y`).
+ `interval=<seconds>` - seconds between reads (default `1`).
+ `timeout=<seconds>` - give up after this many seconds and continue
  (default: wait forever).  A bare trailing number is also accepted as the
  timeout, e.g. `Wait Numbers[0] >= 100 echo=n 30`.

While a `Wait` is running you can press:
+ `q` - stop waiting and continue (skip just this wait).
+ `c` - cancel the running script (the rest of the script is not executed).

For example, wait up to 60 seconds (checking twice a second) for a level tag
to reach its setpoint:
```
Wait Tank_Level >= 750 interval=0.5 timeout=60
```

### Script Commands:
Filenames are case sensitive.
+ ```RunScript <filename>```
    - Validates and then executes a script file.  Each line is a console
      command exactly as it would be typed at the `pylogix_cli>` prompt.
      Blank lines and lines beginning with `#` are ignored.  The script is
      validated first, so if any line contains an unrecognized command the
      script is reported and **not executed at all** (nothing is written to the
      PLC).  A `quit`/`exit` line stops the script early.
+ ```ValidateScript <filename>```
    - Checks a script file for unrecognized commands and reports any problems
      without executing it or touching the PLC.

Because a script can set its own target with the `IPAddress` command, a
self-contained script can be run directly without specifying an IP on the
command line:
```
pylogix_cli RunScript examples/test_script.txt
```
Or from the interactive console:
```
pylogix_cli 192.168.1.10
pylogix_cli> RunScript examples/test_script.txt
```
A worked example script (`examples/test_script.txt`) together with its
supporting tag files is provided in the [`examples/`](examples/) folder.

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

