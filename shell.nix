{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python3
    python3Packages.libclang
    python3Packages.setuptools
    python3Packages.pip
    llvmPackages.clang
    llvmPackages.bintools
  ];

  shellHook = ''
    export PYTHONPATH="${toString ./.}/src:$PYTHONPATH"
    export PYTHONNOUSERSITE=1
    echo "✓ clang-call-analyzer development environment ready"
    echo "✓ Run with: python -m src.cli --help"
  '';
}
