# Automatic Bundy Clock

Bundy clock (punch clock) which automatically checks in on first screen saver unlock and checks out on last screen saver lock for the day.

This project started as a simple way of automatically putting records in a text file on a linux system containing start and end times of a working day. Used for keeping track of flextime and something that could give substance when filling out the weekly time report. Essentially, it's still nothing more than that even though the records are now stored in an sqlite db and could now also be run on both Windows and MacOS.

The main interface is through the CLI but it also has a systray icon where breaks also could be registered, e.g. when going out for lunch. A start of the break is recorded on demand and the break is considered over when the next unlock of the computer happens during the same day. 

## Running the service

Create a virtualenv and install the requirements as usual.

### Linux

Primary target was originally linux systems where the screen saver status could be fetched from dbus. The service is best run with the provided systemd user file but any other means of running a daemon is of course also fine or just simply put something like this in your shell's rc:

```bash
nohup bundyclock -d &
```

### MacOs and Windows

On Mac the service could be started as on linux by putting the command in your shell's rc file. For windows it's recommended to create a shortcut in `shell:startup` to the pythonw version `bundyclockw.exe -d` to avoid creating a terminal window.
