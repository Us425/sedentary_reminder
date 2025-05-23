# StayActive Reminder

StayActive Reminder is a Windows application designed to help users maintain a healthier work routine by reminding them to take regular breaks. It does this by automatically locking the screen after a configurable interval, offering snooze options for flexibility.

## Features

*   **Automatic Screen Lock**: Locks the screen automatically after a user-defined interval.
*   **Snooze Functionality**: Allows users to temporarily postpone the screen lock.
    *   Customizable number of snoozes.
    *   Configurable snooze duration.
*   **Settings GUI**: User-friendly interface to configure:
    *   Screen lock interval.
    *   Snooze enablement and parameters.
*   **Persistent Settings**: All configurations are saved locally in a `settings.json` file.
*   **Automatic Timer Reset**: The main timer automatically resets when the user unlocks their screen after a lock event triggered by the application.
*   **System Tray Icon**: Provides convenient access to:
    *   Open the settings window.
    *   Pause or resume the main timer.
    *   Exit the application.
*   **Windows Session Aware**: Uses Windows events to detect screen lock/unlock for robust timer management (requires `pywin32`).

## Requirements

*   **Operating System**: Windows
*   **Python**: Python 3.x (developed with 3.9)
*   **Libraries**:
    *   `Pillow` (for image manipulation, used by `pystray`)
    *   `pystray` (for creating and managing the system tray icon)
    *   `pywin32` (for Windows-specific features like screen lock detection and locking the workstation)
    *   (Note: `tkinter` is also used, which is part of the Python standard library.)

    These dependencies will be listed in a `requirements.txt` file.

## How to Run from Source

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url> 
    cd <repository_directory_name> 
    ```
    (Replace `<repository_url>` and `<repository_directory_name>` accordingly.)

2.  **Create and Activate Virtual Environment** (Recommended):
    ```bash
    python -m venv venv
    .\venv\Scripts\activate 
    ```
    (On Windows. For other OS, activation command might differ, e.g., `source venv/bin/activate`)

3.  **Install Dependencies**:
    A `requirements.txt` file should be created containing the necessary libraries. Once available, install using:
    ```bash
    pip install -r requirements.txt
    ```
    If `requirements.txt` is not yet available, you can install the main dependencies manually:
    ```bash
    pip install Pillow pystray pywin32
    ```

4.  **Run the Application**:
    ```bash
    python app.py
    ```

## Settings Explanation

The application's behavior can be customized through the Settings window, accessible via the system tray icon.

*   **Screen Lock Interval (minutes)**: Sets how long the application waits (after the timer starts or resets) before initiating a screen lock.
*   **Enable Snooze Feature**: A checkbox to turn the snooze functionality on or off. If unchecked, the screen will lock directly when the main timer expires, without offering a snooze option.
*   **Number of Snoozes Allowed**: If snooze is enabled, this determines how many times the user can snooze the screen lock within a single main timer cycle.
*   **Snooze Duration (minutes)**: If snooze is enabled, this sets the length of each snooze period. After a snooze, the screen will lock unless snoozed again (if allowed).

All settings are saved to `settings.json` in the application's directory when you click "Save Settings".

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

## Contributing

Contributions are welcome! If you have suggestions for improvements or encounter any issues, please feel free to open an issue or submit a pull request on the project's repository.
```
