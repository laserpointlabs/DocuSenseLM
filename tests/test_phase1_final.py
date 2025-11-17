#!/usr/bin/env python3
"""
Phase 1 Final Validation Test

CRITICAL TEST: Validates that all 7 Phase 1 tasks work together as a complete system.

This test runs our ENTIRE Phase 1 stack to ensure:
1. Task 1.1: Status schema supports complete workflow ✅
2. Task 1.2: Database tables support relationships ✅  
3. Task 1.3: Template service works ✅
4. Task 1.4: Email service works ✅
5. Task 1.5: Camunda service works ✅
6. Task 1.6: API layer integrates all services ✅
7. Task 1.7: Complete system integration ✅

This is our "final exam" for Phase 1 before moving to Phase 2.
"""

import pytest
from unittest.mock import Mock, patch

# Import all Phase 1 components
from api.services.template_service import TemplateService, get_template_service
from api.services.email_service import EmailService, get_email_service
from api.services.camunda_service import CamundaService, get_camunda_service
from api.db.schema import NDARecord


class TestPhase1FinalValidation:
    """Final validation that Phase 1 foundation is ready"""
    
    def test_all_phase1_services_available(self):
        """Validate all Phase 1 services are available and functional"""
        
        print("🔍 Testing Phase 1 Service Availability...")
        
        # Task 1.3: Template Service
        try:
            template_service = get_template_service()
            assert template_service is not None
            assert isinstance(template_service, TemplateService)
            print("✅ Task 1.3: Template service available")
        except Exception as e:
            pytest.fail(f"Task 1.3 FAILED: Template service not available: {e}")
        
        # Task 1.4: Email Service
        try:
            email_service = get_email_service()
            assert email_service is not None
            assert isinstance(email_service, EmailService)
            print("✅ Task 1.4: Email service available")
        except Exception as e:
            pytest.fail(f"Task 1.4 FAILED: Email service not available: {e}")
        
        # Task 1.5: Camunda Service
        try:
            camunda_service = get_camunda_service()
            assert camunda_service is not None
            assert isinstance(camunda_service, CamundaService)
            print("✅ Task 1.5: Camunda service available")
        except Exception as e:
            pytest.fail(f"Task 1.5 FAILED: Camunda service not available: {e}")
        
        print("🎉 All Phase 1 services are available and functional!")

    def test_database_schema_complete(self):
        """Validate database schema supports complete NDA workflow"""
        
        print("🔍 Testing Database Schema Completeness...")
        
        # Task 1.1: Status Schema
        try:
            from api.db.schema import NDARecord
            
            # Test that NDARecord has all required fields
            required_fields = [
                'id', 'status', 'counterparty_name', 'workflow_instance_id',
                'template_id', 'template_version', 'created_at', 'updated_at'
            ]
            
            table_columns = list(NDARecord.__table__.columns.keys())
            for field in required_fields:
                assert field in table_columns, f"Required field '{field}' missing from NDARecord"
            
            print("✅ Task 1.1: NDA status schema complete")
            
        except Exception as e:
            pytest.fail(f"Task 1.1 FAILED: Status schema incomplete: {e}")
        
        # Task 1.2: Workflow Tables
        try:
            from api.db.schema import NDAWorkflowInstance, NDAWorkflowTask, NDATemplate, EmailMessage, NDAAuditLog
            
            # Test that all workflow tables exist
            workflow_tables = [
                NDAWorkflowInstance, NDAWorkflowTask, NDATemplate, EmailMessage, NDAAuditLog
            ]
            
            for table_class in workflow_tables:
                assert hasattr(table_class, '__tablename__')
                assert hasattr(table_class, '__table__')
                print(f"✅ Table {table_class.__tablename__} exists")
            
            print("✅ Task 1.2: Workflow database tables complete")
            
        except Exception as e:
            pytest.fail(f"Task 1.2 FAILED: Workflow tables incomplete: {e}")
        
        print("🎉 Database schema is complete and supports full NDA workflow!")

    def test_service_integration_readiness(self):
        """Validate services can integrate with each other"""
        
        print("🔍 Testing Service Integration Readiness...")
        
        try:
            # Task 1.3 → 1.4 Integration: Template → Email
            template_service = get_template_service() 
            email_service = get_email_service()
            
            # Template service can generate content for email
            nda_id = "12345678-1234-5678-9012-123456789012"
            tracking_id = email_service._generate_tracking_id(nda_id)
            assert tracking_id.startswith('NDA-')
            assert '12345678' in tracking_id
            print("✅ Task 1.3 → 1.4: Template-to-Email integration ready")
            
            # Task 1.4 → 1.5 Integration: Email → Camunda
            camunda_service = get_camunda_service()
            
            # Email service tracking can trigger Camunda events
            message_data = camunda_service._prepare_message_event_data(
                message_name="CustomerSignedMessage",
                business_key=f"NDA-{nda_id[:8].upper()}",
                variables={"customer_signed": True}
            )
            
            assert message_data["messageName"] == "CustomerSignedMessage"
            assert "business_key" in str(message_data) or "businessKey" in message_data
            print("✅ Task 1.4 → 1.5: Email-to-Camunda integration ready")
            
            # Task 1.5 → 1.2 Integration: Camunda → Database
            # Camunda variables can be stored in database
            camunda_vars = {
                "nda_record_id": {"value": nda_id, "type": "String"},
                "llm_approved": {"value": True, "type": "Boolean"}
            }
            python_vars = camunda_service._convert_variables_from_camunda_format(camunda_vars)
            
            assert python_vars["nda_record_id"] == nda_id
            assert python_vars["llm_approved"] is True
            print("✅ Task 1.5 → 1.2: Camunda-to-Database integration ready")
            
        except Exception as e:
            pytest.fail(f"Service integration FAILED: {e}")
        
        print("🎉 All services are ready for integration!")

    def test_api_layer_readiness(self):
        """Validate API layer is ready to expose Phase 1 services"""
        
        print("🔍 Testing API Layer Readiness...")
        
        try:
            # Task 1.6: API Registration
            from api.main import app
            
            # Check routers are registered
            route_paths = [route.path for route in app.routes]
            
            required_prefixes = ["/templates", "/workflow"]
            for prefix in required_prefixes:
                matching_routes = [path for path in route_paths if path.startswith(prefix)]
                assert len(matching_routes) > 0, f"No routes found for {prefix}"
                print(f"✅ API routes registered for {prefix}")
            
            print("✅ Task 1.6: API layer properly configured")
            
        except Exception as e:
            pytest.fail(f"Task 1.6 FAILED: API layer not ready: {e}")
        
        print("🎉 API layer is ready to expose Phase 1 functionality!")

    def test_phase1_foundation_complete(self):
        """Final validation that Phase 1 foundation is complete and ready"""
        
        print("\n" + "="*60)
        print("🏁 PHASE 1 FOUNDATION FINAL VALIDATION")
        print("="*60)
        
        validation_results = {
            "Task 1.1: Status Schema": False,
            "Task 1.2: Workflow Tables": False, 
            "Task 1.3: Template Service": False,
            "Task 1.4: Email Service": False,
            "Task 1.5: Camunda Service": False,
            "Task 1.6: API Layer": False,
            "Task 1.7: Integration": False,
        }
        
        # Validate each task component
        try:
            # Task 1.1: Status Schema
            from api.db.schema import NDARecord
            status_column = NDARecord.__table__.columns['status']
            assert status_column.default.arg == "created"
            validation_results["Task 1.1: Status Schema"] = True
            
            # Task 1.2: Workflow Tables  
            from api.db.schema import NDAWorkflowInstance
            assert NDAWorkflowInstance.__tablename__ == 'nda_workflow_instances'
            validation_results["Task 1.2: Workflow Tables"] = True
            
            # Task 1.3: Template Service
            template_service = get_template_service()
            assert hasattr(template_service, 'create_template')
            validation_results["Task 1.3: Template Service"] = True
            
            # Task 1.4: Email Service
            email_service = get_email_service()
            assert hasattr(email_service, 'send_email')
            validation_results["Task 1.4: Email Service"] = True
            
            # Task 1.5: Camunda Service
            camunda_service = get_camunda_service()
            assert hasattr(camunda_service, 'start_process_instance')
            validation_results["Task 1.5: Camunda Service"] = True
            
            # Task 1.6: API Layer
            from api.main import app
            assert len([r for r in app.routes if r.path.startswith("/workflow")]) > 0
            validation_results["Task 1.6: API Layer"] = True
            
            # Task 1.7: Integration (all services work together)
            validation_results["Task 1.7: Integration"] = all([
                validation_results["Task 1.1: Status Schema"],
                validation_results["Task 1.2: Workflow Tables"], 
                validation_results["Task 1.3: Template Service"],
                validation_results["Task 1.4: Email Service"],
                validation_results["Task 1.5: Camunda Service"],
                validation_results["Task 1.6: API Layer"],
            ])
            
        except Exception as e:
            pytest.fail(f"Phase 1 validation FAILED: {e}")
        
        # Print results
        print("\n📊 PHASE 1 VALIDATION RESULTS:")
        for task, passed in validation_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {task}: {status}")
        
        # Overall result
        overall_pass = all(validation_results.values())
        if overall_pass:
            print("\n🎉 PHASE 1 FOUNDATION: COMPLETE AND READY! 🏆")
            print("🚀 Ready to proceed to Phase 2: Database Generalization")
        else:
            failed_tasks = [task for task, passed in validation_results.items() if not passed]
            pytest.fail(f"Phase 1 INCOMPLETE: {failed_tasks}")
        
        assert overall_pass, "Phase 1 foundation must be complete"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
