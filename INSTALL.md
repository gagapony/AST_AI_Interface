# Installation Guide

## NixOS / Nix

**⚠️ Important:** This project requires libclang for AST parsing. On NixOS, you **must** use `nix-shell` to access the clang module.

### Running Tests

Tests must be run inside nix-shell to access the clang module:

```bash
nix-shell shell.nix --run 'pytest tests/'
```

If you encounter `ModuleNotFoundError: No module named 'clang'`, ensure you are running inside nix-shell.

### Using `nix-shell`

On NixOS or systems using Nix package manager, use a development shell:

### Using `nix-shell`

Create a `shell.nix` file:

```nix
{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python3
    python3Packages.clang
    python3Packages.setuptools
    llvmPackages.clang
  ];

  shellHook = ''
    export PYTHONPATH="${toString ./.}/src:$PYTHONPATH"
  '';
}
```

Then run:

```bash
nix-shell
python -m src.cli --help
```

### Using `direnv`

If using `direnv`, create `.envrc`:

```
use nix
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
```

Then run `direnv allow`.

## Traditional Linux (Ubuntu/Debian/Fedora)

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip libclang-dev
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip clang-devel
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python -m src.cli --help
```

## Version Compatibility

Ensure Python `clang` package version matches your system libclang:

```bash
# Check system libclang version
llvm-config --version

# Check Python clang package version
python -c "import clang; print(clang.cindex.conf.get_cxx_library_version())"
```

If versions don't match, install the matching clang package:

```bash
pip install clang==<matching-version>
```
