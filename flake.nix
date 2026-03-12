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
        pname = "icalnotifier";
        version = "0.1.0";
        package = pkgs.python3Packages.buildPythonApplication {
          inherit pname version;
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
        debPackage = bundlers.bundlers.${system}.toDEB package;
        rpmPackage = bundlers.bundlers.${system}.toRPM package;
        appImagePackage = bundlers.bundlers.${system}.toAppImage package;
        distPackage = pkgs.runCommand "${pname}-${version}-dist"
          {
            nativeBuildInputs = [ pkgs.coreutils pkgs.findutils ];
          }
          ''
            mkdir -p "$out"

            deb_file="$(find ${debPackage} -type f -name '*.deb' | head -n 1)"
            rpm_file="$(find ${rpmPackage} -type f -name '*.rpm' | head -n 1)"
            appimage_file="$(find ${appImagePackage} -type f -name '*.AppImage' | head -n 1)"

            cp "$deb_file" "$out/${pname}_${version}_amd64.deb"
            cp "$rpm_file" "$out/${pname}-${version}-1.x86_64.rpm"
            cp "$appimage_file" "$out/${pname}-${version}-x86_64.AppImage"
          '';
      in
      {
        packages.default = package;
        packages.deb = debPackage;
        packages.rpm = rpmPackage;
        packages.appimage = appImagePackage;
        packages.dist = distPackage;

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
            # jsonFormat = pkgs.formats.json { };
            package = cfg.package;
            # configFile = jsonFormat.generate "icalnotifier-settings.json" {
            #   ics_urls = cfg.settings.ics_urls;
            #   notification_minutes = cfg.settings.notification_minutes;
            # };
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
              #xdg.configFile."icalnotifier/settings.json".source = configFile;
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
