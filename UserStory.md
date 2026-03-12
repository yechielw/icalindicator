# Gaol: a linux gui app that notifies before meetings
## requirements
- be able to handle .ics urls include live updates (fetch the url every 1 minute)
- have a systemtray which on right click show all events today
- must be wayland compatiable
- build for all distros should be nix based
- home-manager module should be included
- settings should allow ajusting notificatiuon time
- notification should be audioble
- they tray icon shoud show time in munites until next meeting
- left click on tray item should open the meeting url in browser if present in link (use regex to identify goolge,teams and zoom meetings)
