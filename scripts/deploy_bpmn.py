#!/usr/bin/env python3
"""
Manually deploy BPMN files to Camunda
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.camunda_service import get_camunda_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Deploy BPMN files to Camunda"""
    camunda = get_camunda_service()
    
    # Check if Camunda is accessible
    if not camunda.health_check():
        logger.error("Camunda is not accessible. Is it running?")
        logger.info("Check with: docker compose ps | grep camunda")
        sys.exit(1)
    
    logger.info("Camunda is accessible")
    
    # Find BPMN files
    bpmn_dir = Path(__file__).parent.parent / "camunda" / "bpmn"
    if not bpmn_dir.exists():
        logger.error(f"BPMN directory not found: {bpmn_dir}")
        sys.exit(1)
    
    bpmn_files = list(bpmn_dir.glob("*.bpmn"))
    if not bpmn_files:
        logger.error(f"No BPMN files found in {bpmn_dir}")
        sys.exit(1)
    
    logger.info(f"Found {len(bpmn_files)} BPMN file(s)")
    
    # Deploy each BPMN file
    deployed = 0
    skipped = 0
    failed = 0
    
    for bpmn_file in bpmn_files:
        process_key = bpmn_file.stem
        logger.info(f"\nProcessing: {bpmn_file.name} (process key: {process_key})")
        
        # Check if already deployed
        existing = camunda.get_process_definition_key(process_key)
        if existing:
            logger.info(f"  ✓ Process definition '{process_key}' already deployed (version {existing.get('version', '?')})")
            skipped += 1
            continue
        
        # Deploy the BPMN file
        logger.info(f"  Deploying {bpmn_file.name}...")
        result = camunda.deploy_process_definition(str(bpmn_file))
        if result:
            logger.info(f"  ✓ Successfully deployed: {bpmn_file.name}")
            logger.info(f"    Deployment ID: {result.get('id', 'N/A')}")
            deployed += 1
        else:
            logger.error(f"  ✗ Failed to deploy: {bpmn_file.name}")
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("Deployment Summary:")
    print(f"  Deployed: {deployed}")
    print(f"  Skipped (already deployed): {skipped}")
    print(f"  Failed: {failed}")
    print("="*60)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()






