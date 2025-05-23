# sedentary_reminder

A Windows application to remind users to take breaks and optionally lock their screen. Features include configurable timer intervals, snooze functionality, and a system tray icon for managing the application.

## Features

*   Configurable screen lock timer.
*   Snooze functionality with configurable snooze duration and number of snoozes.
*   Settings are saved locally in `settings.json`.
*   System tray icon for:
    *   Showing settings window.
    *   Pausing/Resuming the timer.
    *   Exiting the application.
*   Timer automatically resets upon screen unlock after a lock event.
*   (Optional) Windows session event listener for screen lock/unlock detection using `pywin32`.
*   (Optional) System tray functionality using `pystray` and `Pillow`.

## Running from Source

1.  Ensure Python 3 is installed.
2.  Clone the repository.
3.  Install dependencies:
    The application attempts to handle optional dependencies gracefully. For full functionality:
    ```bash
    pip install pywin32 pystray Pillow
    ```
    (If a `requirements.txt` file were present, you could use `pip install -r requirements.txt`.)

4.  Run the application:
    ```bash
    python app.py
    ```

## Packaging for Windows (using PyInstaller)

This section describes how to package the application into a standalone executable using `PyInstaller`.

### 1. Prerequisite

Install PyInstaller if you haven't already:
```bash
pip install pyinstaller
```

### 2. Basic Command

A basic command to bundle the application is:
```bash
pyinstaller --windowed --onefile app.py --name StayActiveReminder
```
*   `--windowed`: Prevents a console window from appearing when the application runs. This is suitable as the application uses a system tray icon and Tkinter windows.
*   `--onefile`: Bundles everything into a single executable file.
*   `app.py`: Your main script file.
*   `--name StayActiveReminder`: Sets the name of the executable and the `build`/`dist` folders.

### 3. Application Icon

To specify a custom application icon (`.ico` file) for your executable, use the `--icon` option:
```bash
pyinstaller --windowed --onefile --icon=your_app_icon.ico app.py --name StayActiveReminder
```
Replace `your_app_icon.ico` with the path to your `.ico` file. While the system tray icon is generated programmatically by this application, you can still specify an icon for the executable file itself using this option.

### 4. Data Files (`settings.json`)

The application creates `settings.json` at runtime to store user preferences.
*   When running the packaged executable, `settings.json` will be created in the same directory as the executable if the application has write permissions there. This is the default behavior and requires no special `PyInstaller` flags for the current implementation.
*   If you wanted to bundle a default `settings.json` file (e.g., from a `data/` subdirectory in your source), you would use `PyInstaller`'s `--add-data` option, like:
    ```bash
    # Example: pyinstaller --add-data "data/settings.json:." ...
    # (The ":" specifies the destination relative to the app's root in the bundle)
    ```
    For the current setup, this is not necessary.

### 5. Hidden Imports and Hooks

`PyInstaller` analyzes `app.py` to find dependencies. However, some libraries might need explicit help:

*   **`tkinter`**: Usually handled well by PyInstaller.
*   **`pywin32`** (for Windows session events): This is a complex package. `PyInstaller` might not find all necessary modules. Common hidden imports include:
    *   `win32timezone`
    *   `win32evtlog` (though not directly used, often part of `pywin32`'s typical needs)
*   **`pystray`** (for system tray icon): It uses backends and `PIL` (Pillow). Hidden imports might be needed for specific backends or `PIL` components.
    *   `pystray._win_appindicator` (example, if using a specific backend not automatically detected)
*   **`PIL` (Pillow)**: Sometimes its modules or plugins are not found.
    *   `PIL._tkinter_finder` (if Tkinter support for PIL is needed in a way PyInstaller doesn't see)

If you encounter `ModuleNotFoundError` or similar issues when running the packaged executable, you may need to add `--hidden-import` options.

Example command with potential hidden imports:
```bash
pyinstaller --windowed --onefile app.py --name StayActiveReminder \
--icon=your_app_icon.ico \
--hidden-import=win32timezone \
--hidden-import=pystray._win_appindicator \
--hidden-import=PIL._tkinter_finder
```
The exact hidden imports required can vary based on library versions and your environment. Check `PyInstaller`'s warnings during packaging and runtime error messages for clues. For very complex cases, custom hook files for `PyInstaller` might be necessary.

### 6. Output

`PyInstaller` creates:
*   A `.spec` file (e.g., `StayActiveReminder.spec`): Stores the packaging configuration. You can edit and reuse this file with `pyinstaller StayActiveReminder.spec`.
*   A `build` folder: Contains temporary files from the build process.
*   A `dist` folder: Contains the final packaged application (e.g., `StayActiveReminder.exe` if using `--onefile`). This is the folder/file you would distribute.

After running the command, find your executable in the `dist` directory. Test it thoroughly, including all functionalities like opening settings, pausing/resuming, and ensuring the timer and screen lock/unlock detection work as expected.
```
