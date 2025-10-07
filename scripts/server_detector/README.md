# RuneScape Private Server Detector

A development tool for analyzing RuneScape private server JAR files and detecting their server domains/IPs.

## Features

- **Auto-detection**: Automatically detects launch scripts (.bat, .sh) and their configurations
- **Smart parsing**: Extracts JVM arguments, config URLs, and other launch requirements
- **Network monitoring**: Monitors actual network connections made by the server process
- **Config file scanning**: Parses XML, JSON, properties, and other config files for server addresses
- **Output monitoring**: Monitors server output to extract domain names and IP addresses
- **Fallback detection**: Falls back to direct JAR execution if no launch scripts found
- **Manual intervention support**: Allows manual interaction with dialogs (e.g., detail selection)

## Usage

### Basic Usage

```bash
python -m scripts.server_detector <server_directory>
```

### With Custom Timeout

```bash
python -m scripts.server_detector <server_directory> --timeout 60
```

### Detection Only (No Launch)

```bash
python -m scripts.server_detector <server_directory> --no-launch
```

## Examples

### Example 1: Analyzing RuneRebels Server

```bash
python -m scripts.server_detector ./servers/runerebels/
```

Expected output:
```
Analyzing server directory: ./servers/runerebels/
============================================================

[OK] Configuration detected:
  JAR: Loader.jar
  Working Dir: ./servers/runerebels
  Launch Script: RuneRebels.bat
  Java Args: -Xmx512M -Djava.net.preferIPv4Stack=true
  Config URL: http://www.runerebels.com/resources/config.agf

Scanning config files for server addresses...
No addresses found in config files

============================================================
Launching server to detect domain/IP...
============================================================

Launching: java -Xmx512M -Djava.net.preferIPv4Stack=true -jar Loader.jar -configurl http://www.runerebels.com/resources/config.agf
Monitoring network connections for PID: 12345

Monitoring output and network connections...
(If a dialog appears, please interact with it manually)
[NETWORK] New connection: 104.21.4.253:80 (ESTABLISHED)
[SERVER] RS2 user client - release #317
[NETWORK] New connection: 172.67.154.226:80 (ESTABLISHED)

============================================================
RESULTS
============================================================

[OK] Network connections detected (2):
  - 104.21.4.253:80
  - 172.67.154.226:80

[X] No domains in output

[X] No IPs in output

[OK] Analysis complete!
```

### Example 2: Generic Server with JAR Only

```bash
python -m scripts.server_detector ./servers/custom-server/
```

If no launch scripts are found, the tool will:
1. Locate JAR files in the directory
2. Use default JVM settings (-Xmx512M)
3. Launch and monitor for domains/IPs

## How It Works

1. **Detection Phase**:
   - Scans for launch scripts (.bat, .sh, etc.)
   - Parses scripts to extract java commands and arguments
   - Scans config files (XML, JSON, properties, etc.) for server addresses
   - Falls back to direct JAR detection if no scripts found

2. **Execution Phase**:
   - Launches the server with detected configuration
   - Monitors network connections using `netstat` (Windows) or `lsof` (Unix)
   - Monitors stdout/stderr for domain and IP patterns
   - Uses regex patterns to identify valid domains and IPs
   - Allows manual interaction with dialogs

3. **Analysis Phase**:
   - Reports network connections (most reliable method)
   - Reports config file addresses
   - Reports domains/IPs from output
   - Filters out localhost and invalid addresses
   - Prioritizes domains appearing with server-related keywords

## Supported Launch Patterns

The tool automatically detects:

- **JVM Arguments**: `-Xmx`, `-Xms`, `-XX:`, etc.
- **System Properties**: `-Djava.net.preferIPv4Stack=true`, etc.
- **Config URLs**: `-configurl <url>`
- **JAR Paths**: Relative paths from script location
- **Working Directories**: Proper resolution of paths

## Configuration File Structure

The tool looks for:

```
server-directory/
├── *.bat or *.sh           # Launch scripts
├── *.jar                   # Server JAR files
├── config/                 # Config directories
└── Java/                   # Java-related files (like Loader.jar)
```

## Limitations

- Requires Java to be installed and available in PATH
- Some servers may take longer than the default 30s timeout to establish connections
- Manual interaction required for dialogs (e.g., detail selection in RuneRebels)
- Network monitoring requires appropriate permissions (admin on Windows, may need sudo on Unix)

## Future Enhancements

- [ ] Deep packet inspection for DNS lookups
- [ ] Support for more server types (WoW, etc.)
- [ ] Database connection string detection
- [ ] Automatic dependency detection
- [ ] Automated dialog handling with GUI automation libraries
