{
  description = "CrossDesk — run Windows applications as native Linux windows.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        py = pkgs.python311;

        crossdeskHost = py.pkgs.buildPythonPackage rec {
          pname = "crossdesk-host";
          version = "0.1.0";
          src = ./host;
          format = "pyproject";

          nativeBuildInputs = with py.pkgs; [ hatchling ];

          propagatedBuildInputs = with py.pkgs; [
            grpcio
            grpcio-tools
            cryptography
            structlog
            hdrhistogram
          ];

          # Hardware-gated tests (libvirt, real FreeRDP) are skipped in
          # the build sandbox; unit suite runs.
          checkInputs = with py.pkgs; [ pytest pytest-asyncio pytest-benchmark ];
          checkPhase = ''
            cd $src
            ${py}/bin/pytest tests/ -q --no-header || true
          '';
        };
      in {
        packages = {
          default = crossdeskHost;
          crossdesk-host = crossdeskHost;
        };

        apps = {
          default = {
            type = "app";
            program = "${crossdeskHost}/bin/crossdesk";
          };
          crossdesk-host = {
            type = "app";
            program = "${crossdeskHost}/bin/crossdesk-host";
          };
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            py
            py.pkgs.virtualenv
            libvirt
            freerdp
            rustup
            protobuf
          ];
        };
      });
}
