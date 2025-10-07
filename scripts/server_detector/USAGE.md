# Quick Start Guide

## Installation

No additional dependencies required - uses Python standard library only.

## Basic Usage

### Analyze a server directory:

```bash
python -m scripts.server_detector <path/to/server>
```

This will:
1. Detect launch scripts and configuration
2. Launch the server
3. Monitor output for 30 seconds
4. Extract and display domain names and IPs

### Just detect configuration (no launch):

```bash
python -m scripts.server_detector <path/to/server> --no-launch
```

### Custom timeout:

```bash
python -m scripts.server_detector <path/to/server> --timeout 60
```

## Examples

### RuneRebels Server

```bash
python -m scripts.server_detector test-files/RuneRebels
```

**Output:**
```
[OK] Configuration detected:
  JAR: Loader.jar
  Working Dir: test-files\RuneRebels
  Launch Script: RuneRebels.bat
  Java Args: -Xmx512M -Djava.net.preferIPv4Stack=true
  Config URL: http://www.runerebels.com/resources/config.agf

[OK] Domains found (1):
  - www.runerebels.com

[*] Primary domain: www.runerebels.com
```

### Standalone JAR

```bash
python -m scripts.server_detector path/to/standalone-server/
```

Falls back to default configuration if no launch scripts found.

## Supported Patterns

- **Launch Scripts**: `*.bat`, `*.sh`, `start.*`, `run.*`, `launch.*`
- **JVM Args**: `-Xmx`, `-Xms`, `-D*`, `-XX:*`
- **Config URLs**: `-configurl <url>`
- **JAR Detection**: Prioritizes JARs with "server", "loader", "world" in name

## Tips

1. **Longer timeouts** for slow-starting servers: `--timeout 120`
2. **Config-only checks** for quick verification: `--no-launch`
3. **Look for script files** in the server directory first for best results
4. If domains aren't detected, check server logs manually for connection info

## Programmatic Usage

```python
from scripts.server_detector import ServerDetector, ServerExecutor, OutputAnalyzer
from pathlib import Path

# Detect configuration
detector = ServerDetector(Path('./my-server'))
config = detector.detect()

# Launch and analyze
executor = ServerExecutor(config)
analyzer = OutputAnalyzer()

executor.start()
executor.monitor(analyzer.analyze_line, timeout=30)
executor.stop()

# Get results
domains = analyzer.get_results()['domains']
print(f"Found domains: {domains}")
```
