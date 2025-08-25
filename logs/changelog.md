# Changelog

All notable changes to the Gitea Repo Uploader will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.5] - 2025-08-25

### Fixed

- **Python 3.13 Tkinter Compatibility**: Resolved critical issue where Python 3.13 virtual environments had Tcl/Tk version conflicts preventing GUI from launching
- **Virtual Environment Recreation**: Enhanced launcher scripts to automatically detect and fix tkinter issues by recreating virtual environments with compatible Python versions
- **Dependency Management**: Added requirements.txt for proper dependency management and consistent installations
- **Launcher Script Robustness**: Improved error detection and automatic recovery in both Windows and Linux/macOS launcher scripts

### Changed

- **Dependency Installation**: Now uses requirements.txt instead of hardcoded pip install commands
- **Error Detection**: Enhanced tkinter testing to verify GUI window creation, not just module import
- **Documentation Updates**: Updated all references from pushtogitea.py to app.py across README, troubleshooting guide, and changelog

### Added

- **requirements.txt**: Centralized dependency management file
- **Enhanced Tkinter Testing**: More thorough testing that verifies GUI window creation capability
- **Automatic Python Version Detection**: Launcher scripts now detect and handle Python version compatibility issues
- **Improved Error Messages**: Better diagnostic information when tkinter or virtual environment issues occur

### Technical Changes

- Modified launcher scripts to test GUI window creation instead of just tkinter import
- Added automatic virtual environment recreation when Python version conflicts are detected
- Enhanced error handling for Tcl/Tk library path issues and version mismatches
- Improved fallback mechanisms when virtual environment Python has compatibility issues

## [1.3.4] - 2025-08-24

### Fixed

- **Windows path issues in API uploads**: Normalize paths to POSIX and URL‑encode for Gitea contents API
- **SHA Refresh Logic**: Completely redesigned SHA handling to refresh SHA values before retry attempts
- **Enhanced Error Logging**: Added comprehensive error logging to help diagnose API upload issues
- **Improved Retry Strategy**: Now refreshes SHA from server before retrying failed uploads
- **Better Delete Logic**: Fixed delete+create approach with proper SHA handling for deletions

### Added

- **Detailed Error Reporting**: Upload errors now include full error details and status codes
- **SHA Refresh Mechanism**: Automatically gets fresh SHA values when upload fails due to SHA mismatch
- **Enhanced Debug Logging**: More detailed logging throughout upload process for troubleshooting
- **Success Indicators**: Clear success messages with checkmarks for successful uploads
 - **Non-fast-forward push fallback**: Automatic fetch + merge (-X ours, allow-unrelated-histories) and re-push when remote has existing history

### Improved

- **API Upload Reliability**: Multi-stage approach: normal upload → fresh SHA retry → delete+create; robust path handling across platforms
- **Error Diagnosis**: Better distinction between SHA errors and other types of API errors
- **User Feedback**: More informative progress messages and error explanations

## [1.3.3] - 2025-08-24

### Fixed

- **API Upload SHA Handling**: Completely redesigned SHA error handling to work with any HTTP status code, not just 422
- **Force Overwrite Mode**: Added force overwrite capability for git push fallback scenarios to avoid SHA conflicts entirely
- **Enhanced Error Detection**: Improved detection of SHA-related errors with more robust pattern matching
- **Multi-Stage Retry Logic**: Implemented comprehensive retry strategy: retry without SHA → delete+create → detailed error reporting
- **Better Error Messages**: Added specific error messages for different HTTP status codes (401, 403, 404, 422) with actionable guidance

### Added

- **Force Overwrite Parameter**: New `force_overwrite` parameter in upload functions to bypass existence checks and avoid SHA issues
- **Detailed Logging**: Enhanced logging throughout upload process to help debug issues
- **Multi-Approach Retry**: If SHA retry fails, attempts delete+create approach as final fallback
- **Status Code Reporting**: Upload errors now include HTTP status codes for better debugging

### Improved

- **Git Push Fallback Reliability**: Git push fallback to API upload now uses force overwrite mode to ensure success
- **Upload Success Rate**: Significantly improved success rate for uploading to existing repositories
- **User Feedback**: More informative error messages that explain what went wrong and potential solutions
- **API Upload Robustness**: Enhanced error handling makes API uploads much more reliable in conflict scenarios

### Technical Changes

- Modified `upload_files()` and `upload_directory()` functions to support force overwrite mode
- Enhanced error detection to work across all HTTP status codes
- Improved SHA error pattern matching to catch more variations
- Added comprehensive retry logic with multiple fallback strategies

## [1.3.2] - 2025-08-24

### Fixed

- **Default Repository Naming**: Fixed ZIP file uploads to use ZIP filename (minus extension) as default repository name instead of random temporary directory names
- **Git Push Conflicts**: Added proper handling for git push conflicts when pushing to existing repositories with different history (non-fast-forward errors)
- **API Upload SHA Errors**: Improved API upload fallback to handle SHA requirement errors by retrying without SHA when necessary
- **File Filtering**: Enhanced directory upload to properly exclude .git directories and hidden files from API uploads
- **Error Handling**: Added better error detection and user-friendly messaging for repository conflicts and API upload issues

### Changed

- **Repository Naming Logic**: ZIP files now use their filename as the default repository name, with invalid characters automatically cleaned up
- **Error Messages**: More descriptive error messages when git push fails due to existing repository content
- **Upload Process**: Improved fallback from git push to API upload with better handling of existing files
- **File Processing**: Enhanced file filtering to avoid uploading git metadata and hidden files via API

### Improved

- **User Experience**: Better feedback when operations fail with clear explanations of what went wrong
- **Reliability**: More robust handling of edge cases in both git push and API upload scenarios
- **Performance**: Reduced unnecessary API calls by better file filtering and conflict detection

## [1.3.1] - 2025-08-24

### Fixed

- **Confirmation Dialog Display Issue**: Fixed the "Destructive Action Warning" confirmation dialog where buttons were not visible due to insufficient window height
- **Dialog Layout**: Improved confirmation dialog layout with better padding and element spacing
- **Dialog Sizing**: Increased dialog size from 500x250 to 550x320 pixels to accommodate all content properly
- **User Experience**: Added Enter key binding for faster confirmation workflow
- **Dialog Behavior**: Made confirmation dialog non-resizable for consistent appearance across platforms

### Changed

- **Dialog Structure**: Reorganized confirmation dialog to use a main frame with proper padding for better content organization
- **Spacing Optimization**: Reduced unnecessary padding while ensuring all elements remain clearly visible
- **Visual Polish**: Enhanced dialog appearance with better spacing between warning text, repository information, and action buttons

## [1.3.0] - 2025-08-24

### Added

- **New Management Tab**: Complete repository management interface positioned between Upload and Help tabs
- **Repository Search**: Search and browse repositories accessible to the authenticated user
- **Branch Discovery**: Automatic loading and display of branches for selected repositories
- **Branch Emptying**: Safely delete all files from selected branches while preserving git history
- **Management API Integration**: Uses Gitea REST API for efficient repository and branch operations
- **Enhanced Confirmation System**: Type-to-confirm safety mechanism requiring repository name entry
- **Dedicated Management Logging**: Separate log area for management operations with detailed progress tracking
- **Real-time Progress Monitoring**: Progress bars and status updates for all management operations
- **Background Threading**: Non-blocking operations that keep the UI responsive during long tasks
- **Comprehensive Error Handling**: Detailed error messages with troubleshooting guidance for management failures

### Changed

- **Application Version**: Updated to 1.3.0 to reflect new major functionality
- **Tab Organization**: Management tab now appears between Upload and Help for logical workflow
- **Authentication Integration**: Management features reuse Upload tab credentials for seamless experience
- **Documentation Updates**: Comprehensive updates to README, troubleshooting guide, and changelog
- **API Token Guidance**: Updated documentation to clarify permission requirements for different features

### Security

- **Credential Reuse**: Management features safely reuse authentication from Upload tab without additional storage
- **Secure API Calls**: All management operations use the same secure authentication patterns as upload operations
- **Permission Awareness**: Clear documentation of required token permissions for different management operations
- **Confirmation Safeguards**: Multiple confirmation steps prevent accidental destructive operations

## [1.2.0] - 2025-08-24

### Added

- Integrated automatic tkinter diagnostic and virtual environment repair into main launcher scripts
- Automatic detection and fixing of common Python/tkinter installation issues
- Enhanced launcher scripts with comprehensive error handling and auto-recovery
- Streamlined GUI interface with better space utilization
- **Headless mode**: Terminal windows now close automatically after launching GUI
- **Centered window placement**: GUI now appears in center of screen instead of bottom
- **Professional theming**: Light grey section backgrounds for better visual hierarchy
- **Application icon**: Custom Gitea icon in window title bar and taskbar
- Improved layout with compact progress section and better element visibility

### Changed

- **BREAKING**: Simplified GUI interface by removing optional fields:
  - Removed Owner/Org field (repositories now created under user account)
  - Removed separate Access Token field (unified Password/Token field)
  - Removed Git Identity section (uses username for commits)
- Optimized window geometry for better visibility (800x750 default, min 780x700)
- Enhanced launcher scripts now handle tkinter issues automatically
- Improved error messages and user guidance
- Better space utilization in GUI layout with compact sections
- Changed input field colors from white to light grey for better aesthetics
- Updated section frame backgrounds from white/tan to light grey (#505050)
- Improved window centering algorithm for consistent placement across screen sizes
- Enhanced launcher scripts for truly headless operation with immediate exit
- Reduced padding and improved element spacing for better fit
- Console logging removed in favor of file-only logging for headless operation

### Removed

- Owner/Organization repository support (simplified to user repos only)
- Separate Access Token field (now unified with password field)
- Git Identity configuration options (simplified to use username)
- Helper diagnostic files (fix_venv.bat, fix_tkinter.bat, test_tkinter.py) - functionality integrated into main scripts

### Fixed

- GUI layout issues where buttons were not visible without maximizing window
- Empty grey space that appeared below the "Create New Branch" field
- Window positioning issue (now centers properly on all screen sizes)
- Section frame color inconsistency (white/tan backgrounds now properly themed)
- Tkinter installation problems now automatically detected and resolved
- Virtual environment issues automatically corrected
- Improved error handling throughout the application
- Terminal window persistence issue (now launches in true headless mode with immediate exit)
- Authentication parameter order bug that caused "user does not exist" errors with valid credentials (restored basic auth support)
- Git push network disconnection issues with enhanced timeout and retry logic
- Added automatic API upload fallback when Git push fails due to network issues
- Improved handling of large repositories with better Git buffer configurations
- Cleaned up debug logging for production use

## [1.1.0] - 2025-08-22

### Added

- Progress indicators for file uploads with detailed status information
- Remember last used Gitea URL and username (credentials never saved)
- Enhanced logging system with persistent log files in the logs directory
- Direct drag and drop support for files and folders onto the application window
- Configuration saving and loading system
- Tabbed interface with separate Upload and Help tabs
- Detailed tooltips for easier application usage
- Status indicators for operations with color coding

### Changed

- Enhanced user interface with improved layout and organization
- Enhanced error handling with comprehensive error messages
- Improved API upload process with file-by-file progress updates
- Refined ZIP extraction with progress tracking
- More responsive UI that remains usable during operations
- Better visual feedback for long-running operations

## [1.0.0] - 2025-08-22

### Added

- Initial release of Gitea Repo Uploader
- Cross-platform Python GUI application with gray theme
- Support for both Git push and API-based file upload methods
- Ability to browse folders or accept drag-and-drop paths
- Authentication via Gitea URL, username, and Personal Access Token or password
- Option to extract ZIP files before pushing
- Remote repository creation via Gitea API
- Support for creating and pushing to new branches
- Windows batch wrapper (`run.bat`) that creates/uses virtual environment, installs dependencies, and launches the GUI
- Linux/macOS shell wrapper (`run.sh`) with equivalent functionality
- Comprehensive documentation including README, troubleshooting guide, and changelog

### Security

- Implemented one-shot authentication URLs for Git operations
- No credentials stored in git config
- Option to use Personal Access Tokens instead of passwords
- TLS certificate verification (with option to disable for self-signed certificates)

## ROADMAP [Planned for 1.4.0]

### To Be Added

- **Multi-branch Operations**: Empty multiple branches in a single operation
- **Repository Cloning**: Clone repositories directly through the Management tab
- **Branch Creation**: Create new branches from the Management interface
- **Integration with System Notifications**: Desktop notifications for completed operations
- **Operation History**: Track and display history of management operations

### To Be Improved

- **Enhanced Search**: Advanced filtering and sorting options for repository search
- **Batch Operations**: Perform operations on multiple repositories simultaneously
- **Performance Optimization**: Improve handling of very large repositories
- **Progress Reporting**: More detailed progress information for complex operations

## ROADMAP [Planned for 2.0.0]

### Major Changes

- **Complete UI Redesign**: Modern interface with enhanced usability and accessibility
- **Advanced Repository Management**: Full repository lifecycle management (create, clone, archive, delete)
- **Branch Comparison**: Compare branches and manage merge operations
- **Built-in Conflict Resolution**: Handle merge conflicts directly within the application
- **Custom Git Hooks Support**: Configure and manage repository hooks
- **Multi-Gitea Instance Support**: Manage repositories across multiple Gitea servers
- **Role-based Access Control**: Enhanced permission management for team environments

## Contributing to the Changelog

When contributing to this project, please update the changelog as part of your pull request by adding an entry under the "Unreleased" section at the top of this file.

Use the following categories to organize your changes:

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** in case of vulnerabilities

## Historical Development Notes

### Initial Development (Pre-1.0)

The Gitea Repo Uploader was developed to address the need for a simplified workflow when working with Gitea repositories, particularly for users who needed to upload content without permanently storing credentials or working through the web interface.

Key design decisions:

1. **Using Tkinter** - Chosen for cross-platform compatibility without additional dependencies
2. **Gray Theme** - Selected for reduced eye strain and professional appearance
3. **Dual Upload Methods** - Implemented both Git-based and API-based approaches to accommodate different use cases and systems without Git
4. **Wrapper Scripts** - Created to simplify dependency management and provide platform-specific optimizations
5. **No Credential Storage** - Deliberate decision to prioritize security over convenience

### Acknowledgments

- Gitea API documentation and community for providing the foundation for this tool
- Contributors to the Python requests library which simplifies HTTP operations
- The open-source community for feedback and inspiration