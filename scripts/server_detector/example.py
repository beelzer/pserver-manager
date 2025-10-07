"""
Example usage of the server detector as a library.
"""

from pathlib import Path
from scripts.server_detector import ServerDetector, ServerExecutor, OutputAnalyzer


def analyze_server(server_path: str):
    """Analyze a server directory."""
    detector = ServerDetector(Path(server_path))
    config = detector.detect()

    if not config:
        print("No configuration found")
        return None

    print(f"Found: {config.jar_path}")
    print(f"Args: {config.java_args}")
    if config.config_url:
        print(f"Config URL: {config.config_url}")

    # Launch and analyze
    executor = ServerExecutor(config)
    analyzer = OutputAnalyzer()

    if executor.start():
        executor.monitor(analyzer.analyze_line, timeout=30)
        executor.stop()

        results = analyzer.get_results()
        return results['domains'], results['ips']

    return None, None


if __name__ == '__main__':
    # Example: Analyze RuneRebels server
    domains, ips = analyze_server('./test-files/RuneRebels')
    print(f"\nDomains: {domains}")
    print(f"IPs: {ips}")
