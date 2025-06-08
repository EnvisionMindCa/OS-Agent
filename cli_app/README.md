# Windows CLI Application

This folder contains a standalone command line interface for interacting with
`llm-backend`. The application uses [Typer](https://typer.tiangolo.com/) for a
simple user experience and can be packaged into a single Windows executable
using [PyInstaller](https://www.pyinstaller.org/).

## Running from source

```bash
python -m cli_app --user yourname
```

## Building the executable

1. Install PyInstaller:

   ```bash
   pip install pyinstaller
   ```

2. Build the app:

   ```bash
   pyinstaller --onefile -n llm-chat cli_app/main.py
   ```

   The resulting `llm-chat.exe` will appear in the `dist` directory.

The executable can be distributed on Windows 10/11 systems without requiring a
Python installation.
