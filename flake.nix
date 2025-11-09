{
  description = "A robust Python dev shell for the AlphaEarth Hackathon";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      pythonVersion = pkgs.python311;

      # Nix dependencies for Python itself
      python-nix-deps = [
        pythonVersion
        pkgs.python311Packages.pip
        pkgs.python311Packages.virtualenv
      ];

      # Other tools for your shell
      dev-deps = [
        pkgs.curl
        pkgs.ruff
        pkgs.nodejs
        pkgs.bun
      ];
      
      # These are the C++ libs that pip needs
      build-libraries = [
        pkgs.stdenv.cc.cc.lib
        pkgs.grpc
        pkgs.protobuf
      ];

    in
    {
      devShells.${system}.default = pkgs.mkShell {
        name = "alphaearth-dev";
        packages = python-nix-deps ++ dev-deps;
        buildInputs = build-libraries;

        shellHook = ''
          # --- THIS IS THE NEW FIX ---
          # Forcefully add the C++ standard library to the path
          # so the pip-installed wheels can find it.
          export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"

          # Set up a local venv
          VENV_DIR=".venv"
          if [ ! -d "$VENV_DIR" ]; then
            echo "--- Creating Python virtual environment in $VENV_DIR ---"
            ${pythonVersion}/bin/python -m venv "$VENV_DIR"
          fi
          source "$VENV_DIR/bin/activate"

          # Install packages from requirements.txt
          echo "--- Installing/updating Python packages with pip ---"
          pip install -r requirements.txt

          echo ""
          echo "--- Welcome to the AlphaEarth dev environment ---"
          echo "Your venv is active."
          echo "Run 'cd backend && python app.py' to start the server."
        '';
      };
    };
}
