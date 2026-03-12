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

Build release artifacts with:

```bash
nix build .#dist
ls result
```

This produces:

```text
icalnotifier_0.1.0_amd64.deb
icalnotifier-0.1.0-1.x86_64.rpm
icalnotifier-0.1.0-x86_64.AppImage
```

GitHub releases:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow in [.github/workflows/release.yml](/home/yechiel/tools/icalnotifier/.github/workflows/release.yml) runs `nix flake check`, builds `.#dist`, and uploads the artifacts to the tagged GitHub release.

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
