# Troubleshooting Guide for Gitea Repo Uploader v1.3.4

This document provides solutions for common issues you might encounter when using the Gitea Repo Uploader application.

**Note**: Version 1.2.0 includes automatic problem detection and resolution for most common issues. The launcher scripts will attempt to fix tkinter and virtual environment problems automatically. The application now features true headless operation, centered window placement, and professional theming.

## Table of Contents
- [Automatic Problem Resolution](#automatic-problem-resolution)
- [Installation Issues](#installation-issues)
- [Authentication Problems](#authentication-problems)
- [Git-Related Issues](#git-related-issues)
- [API Errors](#api-errors)
- [ZIP File Handling](#zip-file-handling)
- [Network Connectivity](#network-connectivity)
- [User Interface Issues](#user-interface-issues)
- [Progress Indicators](#progress-indicators)
- [Drag and Drop Functionality](#drag-and-drop-functionality)
- [Configuration and Preferences](#configuration-and-preferences)
- [Logging System](#logging-system)
- [Platform-Specific Problems](#platform-specific-problems)
- [Management Feature Issues](#management-feature-issues)
- [Common Questions (FAQ)](#common-questions-faq)

## Automatic Problem Resolution

**New in v1.2.0**: The application now includes intelligent problem detection and automatic resolution for the most common issues. Additionally, the launcher provides a true headless experience with automatic terminal closure and centered GUI placement.

### Tkinter Issues (Automatic Fix)

**What it does**: When you run `run.bat` (Windows) or `run.sh` (Linux/macOS), the launcher automatically:
1. Tests if tkinter can create GUI windows (not just import) in your virtual environment
2. Detects Python version conflicts (e.g., Python 3.13 Tcl/Tk compatibility issues)
3. If tkinter fails, tests your system Python installation
4. If system Python has working tkinter, automatically recreates the virtual environment
5. Installs dependencies from requirements.txt in the new environment
6. Provides clear error messages if manual intervention is needed

**When manual action is needed**:
- If your system Python also lacks tkinter support
- Windows: Reinstall Python from python.org with "tcl/tk and IDLE" checked
- Linux: Install with `sudo apt-get install python3-tk` (Ubuntu/Debian)

### Virtual Environment Issues (Automatic Fix)

**What it does**: The launcher detects and resolves:
- Corrupted virtual environments
- Virtual environments created with incompatible Python versions (e.g., Python 3.13 with Tcl/Tk version conflicts)
- Missing or broken dependency installations
- Tcl/Tk library path issues and version mismatches

**Recovery process**:
1. Detects the problem automatically
2. Removes the problematic virtual environment
3. Creates a fresh environment with working Python
4. Reinstalls all required dependencies
5. Continues with normal application launch

### When Automatic Fixes Cannot Help

The automatic resolution works for most common cases, but you may need manual intervention if:
- Your system Python installation is fundamentally broken
- You lack write permissions in the application directory
- Your internet connection prevents dependency downloads
- Your system has unusual Python configurations

### Improved Launcher Experience (v1.2.0)

**Headless Operation**: 
- **Windows**: Uses `pythonw.exe` to launch GUI without console window, terminal exits immediately
- **Linux/macOS**: Uses `nohup` to run in background, terminal closes automatically after 2 seconds
- **Window Placement**: GUI automatically centers on screen for optimal visibility across all screen sizes
- **Professional Theming**: Enhanced color scheme with light grey section backgrounds and custom Gitea icon

**What This Means**: When you run `run.bat` or `run.sh`, you'll see minimal terminal output and the GUI will appear centered on your screen with only the application window visible.

## Installation Issues

### Python Not Found

**Symptom:** Error message about Python not being installed or found.

**Solution:** 
- Ensure Python 3.8+ is installed on your system
- Verify Python is in your PATH by running `python --version` or `python3 --version`
- On Windows, try reinstalling Python and checking the "Add Python to PATH" option

### Virtual Environment Creation Fails

**Symptom:** Error when creating the virtual environment.

**Solution:**
- Ensure you have sufficient permissions in the directory
- Try running the wrapper script with administrator/sudo privileges
- Install the `venv` module if it's not included in your Python distribution: `python -m pip install virtualenv`

### Dependency Installation Fails

**Symptom:** Error when installing the required packages.

**Solution:**
- Check your internet connection
- If you're behind a proxy, configure Python's pip to use it
- Dependencies are now managed via requirements.txt: `pip install -r requirements.txt`

## Authentication Problems

### Invalid Credentials

**Symptom:** "Authentication failed" or "403 Forbidden" errors.

**Solution:** 
- Double-check your username and password/token
- Ensure your token has the necessary permissions (at minimum, `write:repository`)
- Check if your account is locked or has 2FA enabled (use token instead of password)

### "User Does Not Exist" Error

**Symptom:** Error message like `'user does not exist [uid: 0, name: ]'` despite valid credentials.

**Solution:** 
- **Fixed in v1.2.0**: This was a parameter order bug that has been resolved by restoring basic authentication support
- The application now properly uses username/password authentication instead of forcing token authentication
- If you still see this error, verify your username and password are correctly entered in the GUI
- Ensure you're not using special characters in your username that might cause parsing issues

### Git Push Network Disconnection

**Symptom:** Errors like `"send-pack: unexpected disconnect while reading sideband packet"` or `"the remote end hung up unexpectedly"` during Git push operations.

**Automatic Fix:** 
- **Fixed in v1.2.0**: The application now automatically detects network disconnection issues
- Enhanced Git configuration with larger buffers and longer timeouts
- Automatic fallback to API upload when Git push fails due to network issues
- Retry logic with smaller chunk sizes for large repositories

**Manual Solutions (if automatic fix doesn't work):** 
- Check your internet connection stability
- Try using "API Upload" mode instead of "Git Push" mode
- If behind a corporate firewall, contact your IT department about Git protocol restrictions
- For very large repositories, consider uploading smaller batches of files

### Token Doesn't Work

**Symptom:** Token authentication fails with 401 errors.

**Solution:**
- Verify the token hasn't expired
- Create a new token in your Gitea instance
- Ensure proper scopes are selected when creating the token (needs `write:repository`)

### Special Characters in Password/Token

**Symptom:** Authentication works in browser but fails in the application.

**Solution:**
- The application URL-encodes credentials, but if you're having issues:
- Avoid special characters in your password
- Use a token instead (recommended)

## Git-Related Issues

### Git Not Found

**Symptom:** "Git is not installed or not on PATH" error.

**Solution:**
- Install Git from [git-scm.com](https://git-scm.com/)
- Ensure Git is added to your PATH
- Alternatively, use the "API Upload" mode which doesn't require Git

### Git Init Fails

**Symptom:** "git init failed" error.

**Solution:**
- Check if you have write permissions in the directory
- Ensure the directory isn't already within another Git repository
- Try initializing Git manually: `git init`

### Push Fails

**Symptom:** "git push failed" error.

**Solution:**
- Check your network connection
- Verify the remote repository exists
- Ensure your credentials have push access
- Check if the branch you're pushing to is protected

### Git Push Rejected (Non-Fast-Forward)

**Symptom:** Git push fails with "fetch first" or "rejected" error, mentioning non-fast-forward updates.

**Solution:**
- **Improved in v1.3.4**: The application now automatically fetches the remote branch,
  merges histories with a merge commit (using `--allow-unrelated-histories` and
  `-X ours` to prefer your local content on conflicts), then pushes again.
- This preserves remote history and avoids manual pull/merge steps.
- If you want a clean slate instead, use the Management tab to empty the branch before uploading.

### Branch Creation Fails

**Symptom:** "Failed to create branch" error.

**Solution:**
- Ensure the branch name follows Git naming conventions
- Check if the branch already exists
- Try creating the branch manually to see specific errors

## API Errors

### API Connection Failed

**Symptom:** Cannot connect to Gitea API or timeout errors.

**Solution:**
- Verify your Gitea URL is correct (including http/https)
- Check if your Gitea instance is running
- Ensure your network can reach the Gitea server

### Repository Already Exists

**Symptom:** 409 or 422 status code when creating a repository.

**Solution:**
- The application will attempt to continue with the existing repository
- If you want a new repository, choose a different name
- You can manually delete the existing repository first

### Organization Access Denied

**Symptom:** Error when trying to create a repo under an organization.

**Solution:**
- Verify you have permission to create repositories in that organization
- Try creating under your personal account instead
- Request appropriate permissions from the organization admin

### Progress Updates Stall

**Symptom:** Upload progress seems to freeze at a certain percentage.

**Solution:**
- For large files, the progress might appear stalled during encoding or API upload
- Wait for the operation to complete as the UI will update when done
- Check the logs for more detailed progress information

### API Upload SHA Errors

**Symptom:** API upload fails with "[SHA]: Required" error messages.

**Solution:**
- **Fixed in v1.3.3 and hardened in v1.3.4**: Enhanced SHA handling plus
  cross-platform path normalization and URL-encoding for contents API calls.
- **Multi-Stage Retry**: normal upload → fresh SHA retry → delete+create.
- **Force Overwrite Path**: When falling back from Git, uploads run in overwrite mode.

**If you still see SHA errors:**
- Check your token has `write:repository` permissions
- Verify the repository and branch exist
- For persistent issues, verify path normalization problems aren’t present on your server and try a different branch/name.

### Wrong Repository Name from ZIP Files

**Symptom:** ZIP files are uploaded to repositories with random names like "gitea_zip_abcd1234" instead of the ZIP filename.

**Solution:**
- **Fixed in v1.3.2**: ZIP files now automatically use their filename (minus .zip extension) as the repository name
- If no repository name is specified, "GiteaPush.zip" will create a repository named "GiteaPush"
- Invalid characters in the filename are automatically replaced with hyphens
- You can still override this by manually entering a repository name before uploading

## ZIP File Handling

### ZIP Extraction Fails

**Symptom:** "Selected .zip is invalid or corrupted" error.

**Solution:**
- Verify the ZIP file is not corrupted (try extracting it manually)
- Check if you have sufficient disk space for extraction
- Try disabling the ZIP extraction feature and handle the files manually

### Extracted Files Missing

**Symptom:** Not all files from the ZIP appear in the repository.

**Solution:**
- Check if the ZIP contains symlinks or other special files not supported
- Ensure no files are ignored by default .gitignore rules
- Try extracting the ZIP manually before uploading

### Extraction Progress Stalls

**Symptom:** ZIP extraction progress seems to freeze.

**Solution:**
- For large ZIP files, extraction might take time
- Check the logs for more detailed progress information
- Ensure you have sufficient disk space for the extracted contents

## Network Connectivity

### TLS/SSL Certificate Errors

**Symptom:** SSL verification errors when connecting to Gitea.

**Solution:**
- If your Gitea server uses a self-signed certificate, you can uncheck "Verify TLS certificates"
- Note that disabling verification reduces security
- Consider installing proper certificates on your Gitea server

### Connection Timeouts

**Symptom:** Operation times out or hangs.

**Solution:**
- Check your internet connection
- Verify Gitea server is responsive
- For large repositories, try pushing smaller batches
- Consider using the API Upload mode for very large repositories

## User Interface Issues

### UI Elements Misaligned

**Symptom:** Interface elements appear misaligned or overlapping.

**Solution:**
- Try resizing the window to at least the minimum size (720x520)
- Ensure your display scaling settings aren't causing issues
- The application uses a fixed gray theme optimized for readability

### Interface Not Responding

**Symptom:** Application freezes during operations.

**Solution:**
- Long operations run in background threads but might still cause brief UI pauses
- Check the log display for progress updates
- For very large operations, allow more time to complete

### Text Display Problems

**Symptom:** Text appears cut off or unreadable.

**Solution:**
- Adjust your system's font scaling
- Resize the window to be larger
- If the gray theme is difficult to read on your system, check if your system has high contrast settings that can help

## Progress Indicators

### Progress Bar Not Updating

**Symptom:** Progress bar doesn't move during operations.

**Solution:**
- For small operations, it might complete too quickly to show progress
- For very large operations, updates might happen in larger increments
- Check the log area for textual progress updates

### Incorrect Progress Percentage

**Symptom:** Progress percentage jumps or seems incorrect.

**Solution:**
- Progress is estimated based on file count/size and might not be linear
- Some operations like API authentication don't contribute to progress
- The operation will complete regardless of progress display issues

### Progress Text Not Updating

**Symptom:** Progress text doesn't change but the bar moves.

**Solution:**
- Check the log area for more detailed status updates
- Restart the application if UI elements become unresponsive
- The operation usually continues correctly despite display issues

## Drag and Drop Functionality

### Drag and Drop Not Working

**Symptom:** Dragging files onto the application window doesn't work.

**Solution:**
- Drag and drop support varies by platform and window manager
- Try dropping onto the path entry field specifically
- Alternatively, use the Browse button or command line arguments
- On Windows, you can also drag onto the .bat file directly

### Wrong Path After Drop

**Symptom:** Path is incorrect or incomplete after dropping.

**Solution:**
- Ensure you're dropping a file or folder, not a shortcut
- Try dragging from a file explorer window directly
- Manually correct the path if needed
- Check for special characters in the path that might be misinterpreted

### Multiple Files Drag Issues

**Symptom:** Can't drag multiple files/folders at once.

**Solution:**
- The application only accepts a single folder or ZIP file at a time
- For multiple folders, place them in a parent folder and drag that
- For multiple files, create a ZIP archive first

## Configuration and Preferences

### Preferences Not Saving

**Symptom:** Settings aren't remembered between sessions.

**Solution:**
- Ensure the "Save Preferences" button is clicked after changes
- Check write permissions for the application directory
- Verify the config.ini file is being created
- If using a read-only location, move the application to a writable directory

### Cannot Create Logs Directory

**Symptom:** Error about creating the logs directory.

**Solution:**
- Ensure you have write permissions for the application directory
- Try running the application with elevated privileges once
- Manually create a logs directory in the same folder as the application

### Config File Corruption

**Symptom:** Application fails to start with config-related errors.

**Solution:**
- Delete the config.ini file to reset to defaults
- Check the file format for manual errors if you edited it
- Ensure no other process is writing to the file simultaneously

## Logging System

### Log Files Not Created

**Symptom:** No log files appear in the logs directory.

**Solution:**
- Ensure the logs directory exists and is writable
- Check if your system has adequate disk space
- Try running the application with elevated privileges once

### Log File Too Large

**Symptom:** Log files grow extremely large.

**Solution:**
- Log files are named with timestamps to prevent overwriting
- Periodically clean up old log files you no longer need
- Log verbosity cannot currently be reduced

### Log Display Slow

**Symptom:** The log text area becomes slow to update.

**Solution:**
- Use the "Clear Log" button to reset the display
- For long operations, focus on the progress bar instead
- Full details are still saved to the log files regardless of display

## Platform-Specific Problems

### Windows Issues

**Symptom:** Path-related errors or Unicode issues on Windows.

**Solution:**
- Avoid non-ASCII characters in file paths
- Try using shorter paths (Windows has path length limitations)
- Run the batch file as administrator if you encounter permission issues

### Linux/macOS Issues

**Symptom:** Permission denied errors when running the script.

**Solution:**
- Ensure the script is executable: `chmod +x run.sh`
- If permission issues persist with Git operations, check file ownership
- For system directories, try running with sudo (not recommended for regular use)

### Display Scaling Issues

**Symptom:** UI appears too small or too large.

**Solution:**
- Tkinter scales based on your system settings
- Adjust your system's display scaling settings
- The application window is resizable to accommodate different displays

## Management Feature Issues

**New in v1.3.0**: The Management tab allows users to empty branches by deleting all files. This section covers common issues with this feature.

### Repository Search Not Working

**Symptom:** "Search Repositories" button returns no results or shows an error.

**Solution:**
- Ensure you have entered valid credentials in the Upload tab (Gitea URL, Username, Password/Token)
- Verify your token has `read:repository` permissions (in addition to `write:repository` for emptying)
- Check that the username exists and owns repositories on the Gitea instance
- Try leaving the search field empty to list all repositories owned by the user
- Check the Management log for detailed error messages

### Cannot Load Branches

**Symptom:** Selecting a repository doesn't populate the branches list.

**Solution:**
- Verify the repository exists and you have access to it
- Ensure your token has `read:repository` permissions
- Check if the repository is empty (no branches exist yet)
- Try refreshing by selecting a different repository and then selecting the original again
- Check the Management log for API error details

### "Empty Selected Branch" Button Disabled

**Symptom:** The button remains grayed out even after selecting repository and branch.

**Solution:**
- Ensure both a repository AND a branch are selected (both labels should show selections)
- Try clicking on the branch name again to ensure it's properly selected
- Verify you're not in the middle of another Management operation
- If the issue persists, restart the application

### Branch Wipe Operation Fails

**Symptom:** Error during the branch emptying process.

**Solution:**
- **Protected Branch**: Check if the branch has protection rules in Gitea that prevent force pushes or deletions
  - Go to Gitea → Repository → Settings → Branches
  - Temporarily disable protection or allow deletions
  - Re-enable protection after the operation
- **Insufficient Permissions**: Ensure your token has `write:repository` and `delete:repository` permissions
- **Network Issues**: Check internet connection and Gitea server availability
- **Large Repository**: For very large repositories, the operation may take longer - wait for completion
- **Git Not Found**: Ensure Git is installed and available in PATH (Management feature requires Git)

### Confirmation Dialog Issues

**Symptom:** Having trouble with the confirmation dialog when wiping a branch.

**Solution:**
- Type the repository name EXACTLY as shown (case-sensitive)
- Only type the repository name, not the full "owner/repo" format
- Ensure there are no extra spaces before or after the text
- The Enter key should work the same as clicking "Confirm Wipe"

**Symptom:** Confirmation dialog buttons not visible or cut off.

**Solution:**
- **Fixed in v1.3.1**: The confirmation dialog now properly sizes to show all content including buttons
- If you're still using an older version, try maximizing or resizing the dialog window
- Ensure your display scaling is set to 100% if you continue to experience issues
- The dialog is now fixed-size (550x320) and should display properly on all standard displays

### Management Log Not Updating

**Symptom:** The Management log area doesn't show progress or error messages.

**Solution:**
- The log is separate from the main Upload log - check the correct log area in the Management tab
- For long operations, messages may appear in batches
- Check the main application log files in the logs/ directory for detailed information
- Try scrolling down in the Management log area as it auto-scrolls to the bottom

### Search Results Show Wrong Repositories

**Symptom:** Search returns repositories that don't belong to the specified user.

**Solution:**
- This is expected behavior when using the search API - it may return repositories from organizations you belong to
- The search is based on the token's permissions, not just user ownership
- To see only user-owned repositories, try using an empty search query
- Filter results manually by looking at the owner/repo format

### Operation Takes Too Long

**Symptom:** Branch wiping operation seems to hang or take excessive time.

**Solution:**
- Large repositories with many files will take longer to process
- The operation involves cloning, deleting files, committing, and pushing - each step takes time
- Check the progress bar and log messages for current status
- Network speed affects cloning and pushing phases
- For repositories with thousands of files, operations may take several minutes

### Authentication Errors in Management Tab

**Symptom:** Management features show authentication errors despite working Upload tab.

**Solution:**
- The Management tab uses the same credentials as the Upload tab
- Ensure you've entered credentials in the Upload tab before using Management features
- Token authentication is preferred over password authentication for API operations
- If using password authentication, some Gitea instances may require token authentication for API access
- Try switching to a Personal Access Token instead of password

### Repository List Shows Duplicates

**Symptom:** The same repository appears multiple times in the search results.

**Solution:**
- This can happen when you belong to repositories through multiple organizations
- The application automatically removes exact duplicates, but similar names may appear
- Look at the full "owner/repo" format to distinguish between repositories
- Choose the correct repository based on the owner name

### Unable to Empty Default Branch

**Symptom:** Operation fails when trying to empty the main/master branch.

**Solution:**
- Some Gitea instances have additional protection on default branches
- Check if the default branch has special protection rules
- Consider temporarily changing the default branch to another branch, emptying the original, then switching back
- Ensure you have administrator permissions on the repository for default branch operations

## Common Questions (FAQ)

### Q: Can I use SSH keys instead of username/password?
A: Not currently. The application uses HTTPS authentication with tokens or passwords.

### Q: Does the tool store my credentials?
A: No. Credentials are only used for the current session and never saved to disk.

### Q: Can I upload to multiple repositories at once?
A: Not in the current version. You need to upload to each repository separately.

### Q: What's the maximum file size that can be uploaded?
A: This depends on your Gitea server configuration. For API uploads, typical limits are around 10MB per file.

### Q: Can I set default values for the fields?
A: You can save your preferred Gitea URL and username with the "Save Preferences" button. Other values need to be entered each time for security reasons.

### Q: Where are log files stored?
A: Log files are stored in the "logs" directory within the application folder, with timestamps in the filenames.

### Q: Can I use the tool without a graphical interface?
A: The current version requires a GUI. A command-line only version is not yet available.

### Q: Can I change the application's theme?
A: The application uses a fixed modern dark theme designed for readability across platforms. Custom themes are not currently supported.

### Q: What happened to the Owner/Org and Git Identity fields?
A: These were removed in v1.2.0 to simplify the interface and ensure all elements fit properly on screen. The application now:
- Creates repositories under your user account automatically
- Uses a unified Password/Token field for authentication
- Uses your username for git commits automatically

### Q: Can I still use Personal Access Tokens?
A: Yes! The Password/Token field accepts either your password or a Personal Access Token. Tokens are still recommended for better security.

### Q: What does the Management tab do?
A: The Management tab (new in v1.3.0) allows you to search your repositories and empty branches by deleting all files. This is useful for clearing out repositories or branches while preserving git history.

### Q: Is the branch emptying operation reversible?
A: No, the operation deletes all files from the selected branch and commits the change. While git history is preserved, the files cannot be automatically recovered. Make sure you have backups before using this feature.

### Q: Why do I need Git installed for the Management feature?
A: The branch emptying operation uses Git commands to clone the repository, delete files, and push changes. This ensures compatibility with standard Git workflows and preserves proper git history.

### Q: Can I empty multiple branches at once?
A: No, the current version only supports emptying one branch at a time. You need to repeat the process for each branch you want to empty.

### Q: What permissions does my token need for Management features?
A: For searching repositories, you need `read:repository` permission. For emptying branches, you need `write:repository` permission. Some operations may also require `delete:repository` permission depending on your Gitea configuration.

### Q: Why does the Management tab show repositories I don't own?
A: The search may return repositories from organizations you belong to or have access to, based on your token's permissions. This is normal behavior - just select the correct repository based on the owner/repo format.

### Q: Can I use the Management feature with protected branches?
A: Protected branches may require additional permissions or temporary removal of protection rules. Check your repository's branch protection settings in Gitea if the operation fails.

### Q: The confirmation dialog buttons are cut off or not visible. What should I do?
A: This issue was fixed in version 1.3.1. If you're using an older version, upgrade to the latest version. The confirmation dialog now properly sizes to 550x320 pixels to ensure all content including buttons are visible. You can also press Enter to confirm or Escape to cancel if the buttons aren't clickable.

### Q: Can I use keyboard shortcuts in the confirmation dialog?
A: Yes! In version 1.3.1 and later, you can press Enter to confirm the branch wipe operation (equivalent to clicking "Confirm Wipe") or Escape to cancel. Just make sure you've typed the repository name correctly first.

### Q: Why does my ZIP file upload to a repository with a random name?
A: This was a bug in versions prior to 1.3.2. Update to the latest version where ZIP files automatically use their filename (minus .zip extension) as the repository name when no specific name is provided.

### Q: What should I do if git push fails with "fetch first" or "rejected" errors?
A: This is automatically handled in version 1.3.2 and later. The application will detect this error (which occurs when pushing to existing repositories with different history) and automatically fall back to API upload to overwrite the existing files. You'll see clear messages explaining what's happening.

### Q: Why do I get "[SHA]: Required" errors during API upload?
A: This was completely resolved in version 1.3.3 with enhanced SHA error handling. The application now uses multiple retry strategies including force overwrite mode in git push fallback scenarios. If you're still seeing these errors, update to the latest version. The new version handles SHA conflicts automatically with comprehensive retry logic.

### Q: Are API uploads reliable when pushing to existing repositories?
A: Yes! Version 1.3.3 introduced force overwrite mode and multi-stage retry logic that makes API uploads highly reliable, especially in git push fallback scenarios. The application will automatically handle file conflicts and SHA mismatches without user intervention.