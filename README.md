# PulseSSH

<p align="center">
  <img width="512" height="512" alt="pulse_ssh" src="https://github.com/user-attachments/assets/bd950657-90c4-4f42-a8c4-131691a56d2d" />
</p>


PulseSSH is a modern terminal manager designed for productivity and ease of use. Manage multiple SSH, MOSH, SFTP, and FTP sessions, organize connections into folders, configure clusters, and customize your workspace with a beautiful UI and advanced automation options.

<img width="930" height="758" alt="image" src="https://github.com/user-attachments/assets/bea56efa-dfab-46ea-942c-b74cc7ee1585" />

*Fig. 1: Dashboard with foldered connections and split terminals.*

## Key Features

### Advanced Terminal Management
- **Multi-Panel & Tabbed Layouts**: Organize terminals in split-pane (vertical/horizontal) or tabbed layouts. Easily switch between views to manage multiple sessions efficiently.
- **Smart Splitting**: Intelligently split terminals from the root or the currently active panel.
- **Local & Remote Terminals**: Seamlessly launch local shell sessions, remote SSH and MOSH connections, and FTP/SFTP file transfers.
- **Customizable Shell**: Define a default shell or specify one per connection.

### Powerful Connection & Session Management
- **Organize with Folders**: Group connections into folders and sub-folders for a clean and structured workspace.
- **Detailed Connection Profiles**: Save SSH, MOSH, FTP, SFTP, and local connections with comprehensive settings:
  - **Credentials**: Store usernames, passwords, and identity file paths.
  - **Sudo**: Configure automatic sudo password entry for privileged commands.
  - **Custom Options**: Set connection timeouts, keep-alive intervals, and more.
- **Search & Filter**: Quickly find connections in the sidebar using the built-in search functionality.

### Clusters for Bulk Operations
- **Batch Sessions**: Group multiple connections into a "Cluster" to launch them all at once.
- **Flexible Launch**: Open cluster connections in separate tabs or a tiled split-pane layout.
- **Easy Selection**: Filter and select which connections from your list to include in a cluster.

### Automation with Scripts & Hooks
- **Connection Hooks**: Automate tasks by running custom scripts at different stages:
  - **Pre/Post-Connect (Local)**: Execute commands on your local machine before connecting or after disconnecting.
  - **Pre/Post-Connect (Remote)**: Run commands on the remote server immediately after login or before logout.
- **Manual Scripts**: Store and run frequently used scripts or command batches on demand.
- **Remote Scripting**: Define scripts that can be executed on the remote machine during a session.

### Deep Customization
- **Appearance**: Tailor the look and feel of your terminal:
  - **Themes**: Switch between light and dark themes.
  - **Fonts & Colors**: Customize the terminal font, size, and color scheme.
  - **Cursor Style**: Choose from block, underline, or bar cursor shapes.
- **Behaviors**: Fine-tune application behavior, such as default split direction, shell selection, and startup settings.
- **Global Settings**:
  - **Binaries**: Define paths to global binaries for use in scripts.
  - **Environment Variables**: Set global environment variables available to all sessions.
  - **Keyboard Shortcuts**: Configure custom keybindings for common actions.

### Security
- **Secure Credential Storage**: Store identity files and manage passphrases securely.
- **Password Protection**: Supports password-based logins for SSH connections.
- **Visibility Toggle**: Hide or show sensitive credentials like passwords and passphrases in the configuration UI.

### User Experience
- **Collapsible Sidebar**: Maximize your terminal workspace with a collapsible sidebar.
- **Intuitive Dialogs**: Easily manage connections, clusters, and settings through clean and organized dialogs.
- **SFTP Integration**: Quickly open an SFTP session for the active terminal to transfer files.
- **FTP Integration**: Quickly open an FTP session for the active terminal to transfer files.
- **Command Palette**: Access commands and actions quickly with a searchable command palette.

- **Cross-Platform**
  - Enjoy a consistent and native experience on Windows, macOS, and Linux.

## Screenshots

### Main Terminal Dashboard
<img width="930" height="758" alt="image" src="https://github.com/user-attachments/assets/b353605f-7111-48b3-9120-1bd192b3c538" />

*Organize connections in the sidebar and manage multiple sessions with split layouts and tabs.*

### Connection Configuration
<img width="850" height="717" alt="image" src="https://github.com/user-attachments/assets/d92d8cc8-67a9-4aab-8b31-a1d88fd17757" />

*Configure connections with detailed settings for authentication, automation scripts, and sudo.*

### Cluster Configuration
<img width="850" height="496" alt="image" src="https://github.com/user-attachments/assets/e5da4859-9b5d-4c60-a5f3-e0d4760aee68" />

*Group connections into a cluster for batch operations, with options for tabbed or split-pane launch.*

### Application Settings
<img width="850" height="496" alt="image" src="https://github.com/user-attachments/assets/8cf70084-8b57-4e00-b259-f89b9435b5ca" />

*Customize appearance, behaviors, shortcuts, and more in the global Settings panel.*

### About PulseSSH
<img width="850" height="496" alt="image" src="https://github.com/user-attachments/assets/7db52841-af92-4457-8583-f9dcace02000" />

*See version information and visit the project website from the About dialog.*
