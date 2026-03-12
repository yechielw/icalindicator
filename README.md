# icalnotifier

Linux tray app that polls ICS feeds, shows today's meetings in the tray menu,
opens the next meeting on left click when supported by the host tray, opens
the events window on middle click, and
notifies before meetings.

Build and test with:

```bash
nix build .#default
nix flake check
```

Run with:

```bash
nix run .#default
```

Home Manager module:

```nix
{
  imports = [ inputs.icalnotifier.homeManagerModules.default ];

  services.icalnotifier = {
    enable = true;
    settings = {
      ics_urls = [ "https://example.com/calendar.ics" ];
      notification_minutes = 10;
    };
  };
}
```
