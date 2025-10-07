"""
RuneScape Private Server Detector
Analyzes server files and extracts domain/IP information.

Usage:
    python -m scripts.server_detector <server_directory> [--timeout SECONDS]
"""

import sys
import argparse
from pathlib import Path

from .detector import ServerDetector
from .executor import ServerExecutor, OutputAnalyzer
from .config_parser import ConfigParser


def main():
    parser = argparse.ArgumentParser(
        description='Detect and analyze RuneScape private server configurations'
    )
    parser.add_argument(
        'server_dir',
        type=Path,
        help='Directory containing server files'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Timeout in seconds for monitoring server output (default: 30)'
    )
    parser.add_argument(
        '--no-launch',
        action='store_true',
        help='Only detect configuration without launching the server'
    )

    args = parser.parse_args()

    if not args.server_dir.exists():
        print(f"Error: Directory not found: {args.server_dir}")
        sys.exit(1)

    print(f"Analyzing server directory: {args.server_dir}")
    print("=" * 60)

    # Detect launch configuration
    detector = ServerDetector(args.server_dir)
    config = detector.detect()

    if not config:
        print("Error: Could not detect server configuration")
        print("No JAR files or launch scripts found")
        sys.exit(1)

    print(f"\n[OK] Configuration detected:")
    print(f"  JAR: {config.jar_path.name}")
    print(f"  Working Dir: {config.working_dir}")
    if config.launch_script:
        print(f"  Launch Script: {config.launch_script.name}")
    if config.java_args:
        print(f"  Java Args: {' '.join(config.java_args)}")
    if config.config_url:
        print(f"  Config URL: {config.config_url}")

    # Parse config files for addresses
    print("\nScanning config files for server addresses...")
    config_parser = ConfigParser(args.server_dir)
    config_addresses = config_parser.find_addresses()

    if config_addresses:
        print(f"Found {len(config_addresses)} address(es) in config files:")
        for addr in sorted(config_addresses):
            print(f"  - {addr}")
    else:
        print("No addresses found in config files")

    if args.no_launch:
        print("\nSkipping server launch (--no-launch specified)")
        if config_addresses:
            print("\nConfig file addresses:")
            for addr in sorted(config_addresses):
                print(f"  - {addr}")
        sys.exit(0)

    print("\n" + "=" * 60)
    print("Launching server to detect domain/IP...")
    print("=" * 60 + "\n")

    # Launch server and analyze output
    executor = ServerExecutor(config)
    analyzer = OutputAnalyzer()

    if not executor.start():
        print("Error: Failed to start server")
        sys.exit(1)

    try:
        # Monitor output
        executor.monitor(analyzer.analyze_line, timeout=args.timeout)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        executor.stop()

    # Display results
    results = analyzer.get_results()
    network_hosts = executor.get_network_hosts()
    game_servers = executor.get_game_servers()
    web_resources = executor.get_web_resources()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    # Show config file addresses (if found)
    if config_addresses:
        print(f"\n[OK] Addresses from config files ({len(config_addresses)}):")
        for addr in sorted(config_addresses):
            print(f"  - {addr}")

    # Show game server connections (most important)
    if game_servers:
        print(f"\n[GAME SERVERS] Likely game world servers ({len(game_servers)}):")
        for host in sorted(game_servers):
            print(f"  * {host}")
    else:
        print("\n[X] No game server connections detected")

    # Show web/CDN connections
    if web_resources:
        print(f"\n[WEB/CDN] Web resources and CDN ({len(web_resources)}):")
        for host in sorted(web_resources):
            print(f"  - {host}")

    # Show all network connections summary
    if network_hosts and not game_servers and not web_resources:
        print(f"\n[OK] Network connections detected ({len(network_hosts)}):")
        for host in sorted(network_hosts):
            print(f"  - {host}")

    # Show domains from output
    if results['domains']:
        print(f"\n[OK] Domains from output ({len(results['domains'])}):")
        for domain in results['domains']:
            print(f"  - {domain}")

        primary = analyzer.get_primary_domain()
        if primary:
            print(f"\n[*] Primary domain: {primary}")
    else:
        print("\n[X] No domains in output")

    # Show IPs from output
    if results['ips']:
        print(f"\n[OK] IPs from output ({len(results['ips'])}):")
        for ip in results['ips']:
            print(f"  - {ip}")
    else:
        print("\n[X] No IPs in output")

    # Exit with appropriate code
    if config_addresses or network_hosts or results['domains'] or results['ips']:
        print("\n[OK] Analysis complete!")
        sys.exit(0)
    else:
        print("\n[!] No connections or addresses detected")
        print("  The server may need more time to initialize,")
        print("  or may not make network connections yet.")
        sys.exit(1)


if __name__ == '__main__':
    main()
