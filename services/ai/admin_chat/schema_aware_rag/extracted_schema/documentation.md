# HIP Healthcare Database Documentation

Generated: 2026-01-06T12:29:50.277872

=== CANONICAL JOIN PATHS ===
These are the CORRECT ways to join tables in this database:

• claims_to_diagnosis:
  Path: claims → diagnoses (via CAST)
  SQL: claims c JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED) WHERE c.diagnosis REGEXP '^[0-9]+$'
  Description: Link claims to diagnoses via claims.diagnosis TEXT column (contains diagnosis ID)

• claims_to_services:
  Path: claims → claims_services → services
  SQL: claims c JOIN claims_services cs ON cs.claims_id = c.id JOIN services s ON s.id = cs.services_id
  Description: Link claims to medical services via junction table

• claims_to_provider:
  Path: claims → providers
  SQL: claims c JOIN providers p ON c.provider_id = p.id
  Description: Link claims to healthcare providers

• claims_to_user:
  Path: claims → users
  SQL: claims c JOIN users u ON c.user_id = u.id
  Description: Link claims to patients (users)

• user_to_state:
  Path: users → states
  SQL: users u JOIN states s ON u.state = s.id
  Description: Link users to their state for geographic filtering

• claims_to_state:
  Path: claims → users → states
  SQL: claims c JOIN users u ON c.user_id = u.id JOIN states s ON u.state = s.id
  Description: Link claims to states via user relationship


=== TABLE DESCRIPTIONS ===

• claims (clinical)
  Description: Healthcare claims submitted by patients
  Rows: ~83,854
  Primary Key: id
  Key Columns: id

• users (users)
  Description: System users (patients, providers, admins)
  Rows: ~1,308,535
  Primary Key: id
  Key Columns: id, role_id
  Foreign Keys: role_id → roles

• service_summaries (clinical)
  Description: Service summary records linking claims to diagnoses
  Rows: ~298,436
  Primary Key: id
  Key Columns: id

• diagnoses (clinical)
  Description: Medical diagnosis codes and names
  Rows: ~34,830
  Primary Key: id
  Key Columns: id

• providers (providers)
  Description: Healthcare providers (hospitals, clinics)
  Rows: ~4,281
  Primary Key: id
  Key Columns: id

• claims_services (clinical)
  Description: Junction table linking claims to services
  Rows: ~363,315
  Primary Key: id
  Key Columns: id

• services (clinical)
  Description: Medical services catalog
  Rows: ~3,578
  Primary Key: id
  Key Columns: id

• states (users)
  Description: Nigerian states for geographic filtering
  Rows: ~718
  Primary Key: id
  Key Columns: id

• dependants (users)
  Description: Patient dependents
  Rows: ~348,451
  Primary Key: id
  Key Columns: id

• health_records (clinical)
  Description: Patient health records
  Rows: ~300,801
  Primary Key: id
  Key Columns: id

• facility_accreditations (providers)
  Description: Provider accreditation status
  Rows: ~6,034
  Primary Key: id
  Key Columns: id

• transactions (financial)
  Description: Financial transactions
  Rows: ~2,348
  Primary Key: id
  Key Columns: id

• authorization_codes (financial)
  Description: Pre-authorization codes for claims
  Rows: ~103,955
  Primary Key: id
  Key Columns: id

• quality_assurances (providers)
  Description: Quality assurance records
  Rows: ~6,008
  Primary Key: id
  Key Columns: id

• drugs (clinical)
  Description: Pharmaceutical drug catalog
  Rows: ~3,948
  Primary Key: id
  Key Columns: id

• activity_log (general)
  Description: 
  Rows: ~1,906,581
  Primary Key: id
  Key Columns: id

• services_renderreds (general)
  Description: 
  Rows: ~411,346
  Primary Key: id
  Key Columns: id

• accreditation_responses (general)
  Description: 
  Rows: ~187,113
  Primary Key: id
  Key Columns: id

• comments (admin)
  Description: Comments on claims/records
  Rows: ~11,341
  Primary Key: id
  Key Columns: id

• documents (admin)
  Description: Uploaded documents
  Rows: ~85,544
  Primary Key: id
  Key Columns: id

• user_dumps (general)
  Description: 
  Rows: ~29,416
  Primary Key: id
  Key Columns: id

• change_providers (general)
  Description: 
  Rows: ~8,641
  Primary Key: id
  Key Columns: id

• quality_assurances_accreditation_services (general)
  Description: 
  Rows: ~6,054
  Primary Key: id
  Key Columns: id

• service_drug_sectors (general)
  Description: 
  Rows: ~2,874
  Primary Key: id
  Key Columns: id

• wards (general)
  Description: 
  Rows: ~2,088
  Primary Key: id
  Key Columns: id

• ministry_models (general)
  Description: 
  Rows: ~1,408
  Primary Key: id
  Key Columns: id

• options (general)
  Description: 
  Rows: ~1,128
  Primary Key: id
  Key Columns: id

• permission_role (general)
  Description: 
  Rows: ~196
  Primary Key: permission_id
  Key Columns: permission_id, role_id
  Foreign Keys: permission_id → permissions, role_id → roles

• data_rows (general)
  Description: 
  Rows: ~454
  Primary Key: id
  Key Columns: id, data_type_id
  Foreign Keys: data_type_id → data_types

• menu_items (general)
  Description: 
  Rows: ~45
  Primary Key: id
  Key Columns: id, menu_id
  Foreign Keys: menu_id → menus

• quality_assurance_items (general)
  Description: 
  Rows: ~915
  Primary Key: id
  Key Columns: id

• local_governments (general)
  Description: 
  Rows: ~775
  Primary Key: id
  Key Columns: id

• claims_paymentorders (general)
  Description: 
  Rows: ~506
  Primary Key: id
  Key Columns: id

• drugs_sub_categories (general)
  Description: 
  Rows: ~201
  Primary Key: id
  Key Columns: id

• permissions (general)
  Description: 
  Rows: ~196
  Primary Key: id
  Key Columns: id

• enrollment_users (general)
  Description: 
  Rows: ~156
  Primary Key: id
  Key Columns: id

• migrations (general)
  Description: 
  Rows: ~186
  Primary Key: id
  Key Columns: id

• ratings (general)
  Description: 
  Rows: ~93
  Primary Key: id
  Key Columns: id

• quality_assurance_items_categories (general)
  Description: 
  Rows: ~88
  Primary Key: id
  Key Columns: id

• paymentorders (general)
  Description: 
  Rows: ~98
  Primary Key: id
  Key Columns: id

• drug_categories (general)
  Description: 
  Rows: ~64
  Primary Key: id
  Key Columns: id

• org_enrolls (general)
  Description: 
  Rows: ~58
  Primary Key: id
  Key Columns: id

• data_types (general)
  Description: 
  Rows: ~37
  Primary Key: id
  Key Columns: id

• authorizationcode_services (general)
  Description: 
  Rows: ~22
  Primary Key: id
  Key Columns: id

• service_categories (general)
  Description: 
  Rows: ~19
  Primary Key: id
  Key Columns: id

• remarks (general)
  Description: 
  Rows: ~25
  Primary Key: id
  Key Columns: id

• forms (general)
  Description: 
  Rows: ~18
  Primary Key: id
  Key Columns: id

• fingerprints (general)
  Description: 
  Rows: ~24
  Primary Key: id
  Key Columns: id

• service_summary_diagnosis (general)
  Description: 
  Rows: ~20
  Primary Key: id
  Key Columns: id

• accreditation_services (general)
  Description: 
  Rows: ~15
  Primary Key: id
  Key Columns: id