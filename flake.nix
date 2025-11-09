{
  description = "AlphaEarth AI Hackathon Environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };


      app-python = (pkgs.python311.withPackages (p: with p; [
        flask
        flask-cors
        geopy
        python-dotenv

        google-generativeai
      ]));

    in
    {
      devShells.${system}.default = pkgs.mkShell {
        
        packages = [
          app-python 
          pkgs.curl     
          pkgs.ruff     
          pkgs.nodejs
          pkgs.bun
        ];

        buildInputs = [
          pkgs.stdenv.cc.cc.lib
        ];

        shellHook = ''
          echo "--- Welcome to the AlphaEarth 'Pure' Nix Shell ---"
          echo "Using Python from: $(which python)"
          echo "All packages (flask, geopy, google-generai) are installed."
          echo ""
          echo "Run 'cd backend && python app.py' to start the server."
        '';
      };
    };
}

