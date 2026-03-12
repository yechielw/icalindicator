{
  description = "icalnotifier";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    bundlers.url = "github:NixOS/bundlers";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    bundlers.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, bundlers, home-manager }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        package = pkgs.python3Packages.buildPythonApplication {
          pname = "icalnotifier";
          version = "0.1.0";
          format = "pyproject";
          src = ./.;
          nativeBuildInputs = [
            pkgs.makeWrapper
            pkgs.qt6.wrapQtAppsHook
            pkgs.python3Packages.setuptools
          ];
          propagatedBuildInputs = with pkgs.python3Packages; [
            icalendar
            platformdirs
            pyside6
            requests
          ];
          buildInputs = [
            pkgs.libcanberra
            pkgs.libnotify
            pkgs.qt6.qtwayland
          ];
          makeWrapperArgs = [
            "--prefix" "PATH" ":" (pkgs.lib.makeBinPath [ pkgs.libnotify pkgs.libcanberra ])
            "--prefix" "XDG_DATA_DIRS" ":" "${pkgs.shared-mime-info}/share"
          ];
          doCheck = true;
          nativeCheckInputs = with pkgs.python3Packages; [
            pytest
          ];
          checkPhase = ''
            runHook preCheck
            pytest tests
            runHook postCheck
          '';
          meta = {
            description = "Linux tray notifier for ICS meeting calendars";
            mainProgram = "icalnotifier";
            platforms = pkgs.lib.platforms.linux;
          };
        };
      in
      {
        packages.default = package;
        packages.deb = bundlers.bundlers.${system}.toDEB package;
        packages.rpm = bundlers.bundlers.${system}.toRPM package;
        packages.appimage = bundlers.bundlers.${system}.toAppImage package;

        apps.default = flake-utils.lib.mkApp {
          drv = package;
        };

        checks.default = package;

        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.libcanberra
            pkgs.libnotify
            pkgs.qt6.qtwayland
            (pkgs.python3.withPackages (ps: with ps; [
              icalendar
              platformdirs
              pyside6
              pytest
              requests
              setuptools
            ]))
          ];
        };
      }) // {
        homeManagerModules.default = { config, lib, pkgs, ... }:
          let
            cfg = config.services.icalnotifier;
            jsonFormat = pkgs.formats.json { };
            package = cfg.package;
            configFile = jsonFormat.generate "icalnotifier-settings.json" {
              ics_urls = cfg.settings.ics_urls;
              notification_minutes = cfg.settings.notification_minutes;
            };
          in
          {
            options.services.icalnotifier = {
              enable = lib.mkEnableOption "icalnotifier";
              package = lib.mkOption {
                type = lib.types.package;
                default = self.packages.${pkgs.system}.default;
              };
              settings = lib.mkOption {
                type = lib.types.submodule {
                  options = {
                    ics_urls = lib.mkOption {
                      type = lib.types.listOf lib.types.str;
                      default = [ ];
                    };
                    notification_minutes = lib.mkOption {
                      type = lib.types.int;
                      default = 10;
                    };
                  };
                };
                default = { };
              };
            };

            config = lib.mkIf cfg.enable {
              home.packages = [ package ];
              xdg.configFile."icalnotifier/settings.json".source = configFile;
              systemd.user.services.icalnotifier = {
                Unit = {
                  Description = "icalnotifier tray app";
                  PartOf = [ "graphical-session.target" ];
                  After = [ "graphical-session.target" ];
                };
                Service = {
                  ExecStart = "${package}/bin/icalnotifier";
                  Restart = "on-failure";
                  Environment = "QT_QPA_PLATFORM=wayland;xcb";
                };
                Install = {
                  WantedBy = [ "graphical-session.target" ];
                };
              };
            };
          };
      };
}
