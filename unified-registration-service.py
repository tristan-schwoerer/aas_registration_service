#!/usr/bin/env python3
"""
Unified AAS Registration Service - CLI Entry Point

This service:
1. Parses JSON configuration files matching the ResourceTypeAAS schema
2. Deep-merges them with the asset template (Pydantic validation)
3. Generates AAS descriptions via the Pydantic + BaSyx pipeline
4. Registers AAS and submodels with BaSyx server

The AAS is the single source of truth — no topics.json / DataBridge /
Operation-Delegation processing happens here anymore.

Usage:
    # Register from JSON config
    python unified-registration-service.py register-config path/to/config.json

    # Register all configs from a directory
    python unified-registration-service.py register-dir path/to/configs/

    # Start MQTT listener for config-based registration
    python unified-registration-service.py listen

    # List registered AAS
    python unified-registration-service.py list
"""

import argparse
import logging
import sys
from pathlib import Path

from src import (
    BaSyxConfig,
    UnifiedRegistrationService,
    MQTTConfigRegistrationService,
)
from src.core.constants import (
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_BASYX_URL,
    MQTTTopics
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Unified AAS Registration Service - Register assets from JSON configs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Register from JSON config (in Docker):
    %(prog)s register-config AASDescriptions/Resource/configs/syntegonStoppering.json

  Register from JSON config (from the host, with registry URLs):
    %(prog)s --basyx-url http://localhost:8081 \
      --aas-registry-url http://localhost:8082 \
      --sm-registry-url http://localhost:8083 \
      register-config ../AASDescriptions/Resource/configs/syntegonStoppering.json

  Register all configs from directory:
    %(prog)s register-dir AASDescriptions/Resource/configs/

  Start MQTT listener:
    %(prog)s listen --mqtt-broker 192.168.0.104

  List registered AAS:
    %(prog)s list
        """
    )

    # Global options
    parser.add_argument('--basyx-url', default=DEFAULT_BASYX_URL,
                        help=f'BaSyx server base URL (default: {DEFAULT_BASYX_URL})')
    parser.add_argument('--aas-registry-url', default=None,
                        help='AAS registry base URL, e.g. http://localhost:8082 '
                             '(default: in-container http://aas-registry:8080)')
    parser.add_argument('--sm-registry-url', default=None,
                        help='Submodel registry base URL, e.g. http://localhost:8083 '
                             '(default: in-container http://sm-registry:8080)')
    parser.add_argument('--mqtt-broker', default=DEFAULT_MQTT_BROKER,
                        help=f'MQTT broker hostname/IP (default: {DEFAULT_MQTT_BROKER})')
    parser.add_argument('--mqtt-port', type=int, default=DEFAULT_MQTT_PORT,
                        help=f'MQTT broker port (default: {DEFAULT_MQTT_PORT})')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    # Subcommands
    subparsers = parser.add_subparsers(
        dest='command', help='Command to execute')

    # Register from JSON config (primary command)
    config_parser = subparsers.add_parser('register-config',
                                          help='Register asset from JSON config file')
    config_parser.add_argument('config_file', type=str,
                               help='Path to JSON configuration file')

    # Register from directory
    dir_parser = subparsers.add_parser('register-dir',
                                       help='Register all assets from config directory')
    dir_parser.add_argument('config_dir', type=str,
                            help='Directory containing JSON config files')

    # MQTT Listener
    listen_parser = subparsers.add_parser('listen',
                                          help='Start MQTT listener for registration')
    listen_parser.add_argument('--config-topic', default=MQTTTopics.REGISTRATION_CONFIG,
                               help='MQTT topic for config registration')
    listen_parser.add_argument('--response-topic', default=MQTTTopics.REGISTRATION_RESPONSE,
                               help='MQTT topic for responses')

    # List registered AAS
    list_parser = subparsers.add_parser('list', help='List all registered AAS')

    # Configure
    configure_parser = subparsers.add_parser('configure',
                                             help='Show/update configuration')

    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate command
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        # Initialize BaSyx configuration (registry URLs default to the
        # in-container hostnames; pass --aas-registry-url/--sm-registry-url
        # when running from the host)
        basyx_config = BaSyxConfig(
            base_url=args.basyx_url,
            aas_registry_url=args.aas_registry_url,
            sm_registry_url=args.sm_registry_url,
        )

        # Execute command
        if args.command == 'register-config':
            # Register from JSON config
            config_path = Path(args.config_file)
            if not config_path.exists():
                logger.error(f"Config file not found: {config_path}")
                sys.exit(1)

            service = UnifiedRegistrationService(config=basyx_config)

            logger.info(f"Registering from config: {config_path}")
            success = service.register_from_config(config_path=str(config_path))

            if success:
                logger.info("✓ Registration completed successfully")
                sys.exit(0)
            else:
                logger.error("✗ Registration failed")
                sys.exit(1)

        elif args.command == 'register-dir':
            # Register from directory
            config_dir = Path(args.config_dir)
            if not config_dir.exists():
                logger.error(f"Config directory not found: {config_dir}")
                sys.exit(1)

            config_paths = list(config_dir.glob('*.json'))
            if not config_paths:
                logger.error(f"No JSON files found in {config_dir}")
                sys.exit(1)

            service = UnifiedRegistrationService(config=basyx_config)

            logger.info(
                f"Registering {len(config_paths)} configs from {config_dir}")
            results = service.register_multiple_configs(
                [str(p) for p in config_paths]
            )

            successful = sum(1 for s in results.values() if s)
            if successful == len(results):
                logger.info(f"✓ All {successful} registrations completed")
                sys.exit(0)
            elif successful > 0:
                logger.warning(
                    f"⚠ {successful}/{len(results)} registrations completed")
                sys.exit(0)
            else:
                logger.error("✗ All registrations failed")
                sys.exit(1)

        elif args.command == 'listen':
            # Start MQTT listener
            service = UnifiedRegistrationService(config=basyx_config)

            mqtt_service = MQTTConfigRegistrationService(
                registration_service=service,
                mqtt_broker=args.mqtt_broker,
                mqtt_port=args.mqtt_port,
                config_topic=args.config_topic,
                response_topic=args.response_topic
            )

            logger.info("Starting MQTT registration listener...")
            logger.info(f"MQTT Broker: {args.mqtt_broker}:{args.mqtt_port}")
            logger.info(f"Config Topic: {args.config_topic}")

            try:
                mqtt_service.start()
                logger.info("✓ MQTT listener started. Press Ctrl+C to stop.")
                logger.info("\nUnified Service running with:")
                logger.info("  - MQTT registration listener (deep merge → AAS → post to BaSyx)")
                logger.info("\nSupported config message formats:")
                logger.info("1. Raw YAML (from ESP32 devices):")
                logger.info("   syntegonStopperingSystemAAS:")
                logger.info("     idShort: syntegonStopperingSystemAAS")
                logger.info("     ...")
                logger.info("")
                logger.info("2. JSON wrapper (from other clients):")
                logger.info('{')
                logger.info('  "requestId": "unique-id",')
                logger.info('  "assetId": "asset-identifier",')
                logger.info('  "config": { ... yaml config as JSON ... }')
                logger.info('}\n')

                while True:
                    import time
                    time.sleep(1)

            except KeyboardInterrupt:
                logger.info("\nShutting down...")
                mqtt_service.stop()

                stats = mqtt_service.get_stats()
                logger.info(f"\nStatistics:")
                logger.info(f"  Config received: {stats['config_received']}")
                logger.info(f"  Processed: {stats['processed']}")
                logger.info(f"  Failed: {stats['failed']}")

                sys.exit(0)

        elif args.command == 'list':
            service = UnifiedRegistrationService(config=basyx_config)

            registered = service.list_registered_assets()
            shells = registered.get('aas_shells', [])
            submodels = registered.get('submodels', [])

            if shells:
                logger.info(f"\nRegistered AAS Shells ({len(shells)}):")
                for shell in shells:
                    logger.info(f"  • {shell.get('idShort', 'Unknown')}")
                    logger.info(f"    ID: {shell.get('id', 'Unknown')}")
            else:
                logger.info("\nNo AAS shells registered")

            if submodels:
                logger.info(f"\nRegistered Submodels ({len(submodels)}):")
                for sm in submodels:
                    logger.info(f"  • {sm.get('idShort', 'Unknown')}")

            sys.exit(0)

        elif args.command == 'configure':
            logger.info("Current configuration:")
            logger.info(f"  BaSyx URL: {args.basyx_url}")
            logger.info(f"  MQTT Broker: {args.mqtt_broker}:{args.mqtt_port}")
            sys.exit(0)

        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.debug)
        sys.exit(1)


if __name__ == "__main__":
    main()
