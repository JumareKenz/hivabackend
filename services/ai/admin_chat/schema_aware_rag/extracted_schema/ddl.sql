-- DDL for HIP Healthcare Database
-- Extracted: 2026-01-06T12:29:50.277666
-- Tables: 50

-- Healthcare claims submitted by patients
-- Rows: ~83,854
CREATE TABLE `claims` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` INT NOT NULL,
  `provider_id` INT NOT NULL,
  `agency_id` INT NOT NULL,
  `client_name` VARCHAR NOT NULL,
  `claim_unique_id` VARCHAR,
  `seen_date` DATE NOT NULL,
  `diagnosis` TEXT NOT NULL,
  `treatment` TEXT NOT NULL,
  `claim_level` VARCHAR,
  `status` INT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `client_id` INT,
  `authorization_code` VARCHAR,
  `total_cost` DOUBLE,
  `prepared_by_id` INT,
  `checked_by_id` INT,
  `verified_by_id` INT,
  `approved_by_id` INT,
  `prepared_by_date` DATE,
  `checked_by_date` DATE,
  `verified_by_date` DATE,
  `approved_by_date` DATE,
  `is_signed` TINYINT,
  `org_id` INT,
  `dependent_id` INT,
  `is_out_of_station` TINYINT NOT NULL DEFAULT 0,
  `deleted_at` TIMESTAMP
);

-- System users (patients, providers, admins)
-- Rows: ~1,308,535
CREATE TABLE `users` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `role_id` BIGINT,
  `agency_id` INT,
  `provider_id` INT,
  `picture` VARCHAR,
  `firstname` VARCHAR,
  `lastname` VARCHAR,
  `agency_name` VARCHAR,
  `email` VARCHAR,
  `tribe` VARCHAR DEFAULT users/default.png,
  `phone_number` VARCHAR,
  `user_image` VARCHAR,
  `user_image_updated_at` DATE,
  `email_verified_at` TIMESTAMP,
  `password` VARCHAR,
  `state` VARCHAR,
  `localgovt` INT,
  `address1` VARCHAR,
  `ward` VARCHAR,
  `type` VARCHAR NOT NULL,
  `institutional_id` INT,
  `job_title` VARCHAR,
  `means_of_id` VARCHAR,
  `state_of_origin` VARCHAR,
  `lga_of_origin` TEXT,
  `recipient_code` VARCHAR,
  `dob` DATE,
  `gender` VARCHAR,
  `date_id_card_issued` DATE,
  `education` VARCHAR,
  `blood` VARCHAR,
  `genotype` VARCHAR,
  `remember_token` VARCHAR,
  `settings` JSON,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `user_role` VARCHAR DEFAULT 0,
  `id_card_number` VARCHAR,
  `previous_user_id` BIGINT,
  `virtual_account` VARCHAR,
  `point_of_care` VARCHAR,
  `sector` VARCHAR,
  `salary_number` VARCHAR,
  `religion` VARCHAR,
  `place_of_work` VARCHAR,
  `nimc_number` VARCHAR,
  `middlename` VARCHAR,
  `grade_level` VARCHAR,
  `date_of_entry` VARCHAR,
  `marital_status` VARCHAR,
  `category_of_vulnerable_group` VARCHAR,
  `community` VARCHAR,
  `alternate_provider_id` VARCHAR,
  `signature` VARCHAR,
  `facility_code` VARCHAR,
  `enrolled_by` VARCHAR,
  `org_id` INT,
  `lga` INT,
  `occupation` VARCHAR,
  `phc_sector` VARCHAR,
  `phc_type` VARCHAR,
  `phc_general` VARCHAR,
  `sectorType` VARCHAR,
  `special_need` VARCHAR,
  `expiry_date` DATE,
  `blocked_at` TIMESTAMP,
  `enabled_user` TINYINT NOT NULL DEFAULT 1,
  `plan_type` VARCHAR,
  `deleted_at` TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`)
);

-- Service summary records linking claims to diagnoses
-- Rows: ~298,436
CREATE TABLE `service_summaries` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `provider_id` INT,
  `client_id` INT,
  `diagnosis` INT,
  `encounter_outcome` VARCHAR DEFAULT 0,
  `authorization_code` VARCHAR,
  `treatment_type` VARCHAR,
  `date_of_admission` DATE,
  `date_of_discharge` DATE,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `health_record_id` INT,
  `agency_id` INT NOT NULL,
  `claim_id` INT,
  `dependent_id` INT,
  `secondary_diagnosis` INT,
  `is_confirmed` TINYINT,
  `is_underlying` TINYINT NOT NULL DEFAULT 0,
  `deleted_at` TIMESTAMP
);

-- Medical diagnosis codes and names
-- Rows: ~34,830
CREATE TABLE `diagnoses` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `name` VARCHAR,
  `symptoms` TEXT,
  `agency_id` INT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `transmission` TEXT,
  `diagnosis` TEXT,
  `treatment` TEXT,
  `prevention` TEXT,
  `diagnosis_code` VARCHAR,
  `is_primary` TINYINT NOT NULL DEFAULT 0,
  `deleted_at` TIMESTAMP
);

-- Healthcare providers (hospitals, clinics)
-- Rows: ~4,281
CREATE TABLE `providers` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT NOT NULL,
  `provider_id` VARCHAR NOT NULL,
  `status` TINYINT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

-- Junction table linking claims to services
-- Rows: ~363,315
CREATE TABLE `claims_services` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `claims_id` INT,
  `services_id` INT,
  `drugs_id` INT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `cost` DOUBLE NOT NULL,
  `remark_id` INT,
  `dose` INT NOT NULL DEFAULT 1,
  `frequency` INT NOT NULL DEFAULT 1,
  `days` INT NOT NULL DEFAULT 1,
  `vetted_price` DOUBLE,
  `verified_price` DOUBLE,
  `vetted_dose` INT NOT NULL DEFAULT 1,
  `vetted_frequency` INT NOT NULL DEFAULT 1,
  `vetted_days` INT NOT NULL DEFAULT 1,
  `verified_dose` INT NOT NULL DEFAULT 1,
  `verified_frequency` INT NOT NULL DEFAULT 1,
  `verified_days` INT NOT NULL DEFAULT 1
);

-- Medical services catalog
-- Rows: ~3,578
CREATE TABLE `services` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `service_category_id` INT,
  `kgshia_code` VARCHAR,
  `price` DOUBLE,
  `description` TEXT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `agency_id` INT
);

-- Nigerian states for geographic filtering
-- Rows: ~718
CREATE TABLE `states` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `name` VARCHAR NOT NULL,
  `country_id` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

-- Patient dependents
-- Rows: ~348,451
CREATE TABLE `dependants` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` INT,
  `enrolle_number` VARCHAR,
  `firstname` VARCHAR NOT NULL,
  `lastname` VARCHAR,
  `email` VARCHAR,
  `phone_number` VARCHAR,
  `relationShipType` VARCHAR NOT NULL,
  `provider` INT,
  `dob` DATE,
  `gender` VARCHAR,
  `image` VARCHAR,
  `state` VARCHAR,
  `lga` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `middle_name` VARCHAR,
  `institution_attending` VARCHAR,
  `enrolled_by` INT,
  `id_card_number` VARCHAR,
  `agency_id` INT NOT NULL,
  `expiry_date` DATE,
  `enabled_user` TINYINT NOT NULL DEFAULT 1,
  `is_civil_servant` TINYINT NOT NULL DEFAULT 0,
  `nimc_number` VARCHAR,
  `deleted_at` TIMESTAMP,
  `blood` VARCHAR
);

-- Patient health records
-- Rows: ~300,801
CREATE TABLE `health_records` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `provider_id` INT,
  `professional_id` INT NOT NULL,
  `appointment_id` INT,
  `patient_id` INT NOT NULL,
  `reasonVisit` TEXT,
  `testResult` TEXT,
  `drVisited` VARCHAR,
  `medications` TEXT NOT NULL,
  `documents` VARCHAR NOT NULL,
  `notes` TEXT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `date_of_visit` DATE,
  `encounter_id` VARCHAR NOT NULL,
  `dependent_id` INT
);

-- Provider accreditation status
-- Rows: ~6,034
CREATE TABLE `facility_accreditations` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `quality_assurance_id` INT NOT NULL,
  `name_of_facility` INT NOT NULL,
  `address` VARCHAR NOT NULL,
  `ward` INT NOT NULL,
  `localgovt` INT NOT NULL,
  `state` INT NOT NULL,
  `phone_number` VARCHAR,
  `email` VARCHAR,
  `facility_type` VARCHAR NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

-- Financial transactions
-- Rows: ~2,348
CREATE TABLE `transactions` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT,
  `provider_id` INT,
  `user_id` INT,
  `description` TEXT,
  `amount` DOUBLE,
  `type` VARCHAR,
  `status` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `transaction_ref` MEDIUMTEXT NOT NULL,
  `batch_id` INT
);

-- Pre-authorization codes for claims
-- Rows: ~103,955
CREATE TABLE `authorization_codes` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT NOT NULL,
  `requested_by` INT,
  `created_by` INT,
  `principal_id` INT,
  `dependent_id` INT,
  `code_created` VARCHAR,
  `date_requested` DATE NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `expiry_date` DATE,
  `is_code_used` TINYINT NOT NULL DEFAULT 0,
  `provider_id` INT,
  `org_id` INT,
  `service_summary_id` INT,
  `referred_to_facility` INT,
  `status` VARCHAR NOT NULL DEFAULT pending,
  `is_corridor` TINYINT NOT NULL DEFAULT 0,
  `secondary_agency_id` BIGINT,
  `deleted_at` TIMESTAMP
);

-- Quality assurance records
-- Rows: ~6,008
CREATE TABLE `quality_assurances` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `facility_id` INT,
  `form_id` BIGINT NOT NULL DEFAULT 1,
  `accreditation_category` VARCHAR,
  `quality_assurance_type` VARCHAR,
  `name_of_contact_person` VARCHAR,
  `signature_of_contact_person` VARCHAR,
  `team_leader` VARCHAR,
  `signature_of_monitoring_team_leader` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `agency_id` INT NOT NULL,
  `status` VARCHAR NOT NULL DEFAULT pending,
  `further_comments` TEXT
);

-- Pharmaceutical drug catalog
-- Rows: ~3,948
CREATE TABLE `drugs` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `drug_name` VARCHAR NOT NULL,
  `dosage` VARCHAR NOT NULL,
  `strengths` VARCHAR,
  `presentation` VARCHAR,
  `price` DOUBLE NOT NULL,
  `sub_category_id` INT,
  `category_id` INT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `agency_id` INT,
  `unit` VARCHAR,
  `primary_price` DOUBLE,
  `secondary_price` DOUBLE,
  `tertiary_price` DOUBLE
);

CREATE TABLE `activity_log` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `log_name` VARCHAR,
  `description` TEXT NOT NULL,
  `subject_type` VARCHAR,
  `subject_id` BIGINT,
  `causer_type` VARCHAR,
  `causer_id` BIGINT,
  `properties` JSON,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `services_renderreds` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `service_summary_id` INT,
  `service_id` INT,
  `drug_id` INT,
  `service_type` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `dose` INT NOT NULL,
  `frequency` INT NOT NULL,
  `days` INT NOT NULL,
  `total_cost` DOUBLE NOT NULL
);

CREATE TABLE `accreditation_responses` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `quality_assurance_id` INT NOT NULL,
  `quality_assurance_item_id` INT NOT NULL,
  `response` VARCHAR NOT NULL,
  `score` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

-- Comments on claims/records
-- Rows: ~11,341
CREATE TABLE `comments` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` INT NOT NULL,
  `claim_id` INT,
  `body` MEDIUMTEXT NOT NULL,
  `service_summary_id` INT,
  `provider_id` INT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `complaint_id` INT,
  `authorization_code_id` INT,
  `claim_service_id` INT,
  `transaction_id` BIGINT
);

-- Uploaded documents
-- Rows: ~85,544
CREATE TABLE `documents` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT,
  `provider_id` INT,
  `user_id` VARCHAR,
  `type` VARCHAR NOT NULL,
  `type_id` INT,
  `document` VARCHAR NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `name` VARCHAR,
  `previous_user_id` BIGINT,
  `deleted_at` DATE
);

CREATE TABLE `user_dumps` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` INT,
  `agency_id` INT,
  `provider_id` INT,
  `picture` VARCHAR,
  `firstname` VARCHAR,
  `lastname` VARCHAR,
  `agency_name` VARCHAR,
  `email` VARCHAR,
  `phone_number` VARCHAR,
  `user_image` LONGTEXT,
  `nimc_number` VARCHAR,
  `email_verified_at` TIMESTAMP,
  `password` VARCHAR,
  `state` VARCHAR,
  `localgovt` VARCHAR,
  `address1` VARCHAR,
  `ward` VARCHAR,
  `type` VARCHAR,
  `institutional_id` INT,
  `job_title` VARCHAR,
  `agencyAddress` VARCHAR,
  `agencyWebsite` VARCHAR,
  `agencyDescription` TEXT,
  `agencyActive` INT,
  `dob` DATE,
  `middlename` VARCHAR,
  `marital_status` VARCHAR,
  `category_of_vulnerable_group` VARCHAR,
  `enrolled_by` VARCHAR,
  `org_id` VARCHAR,
  `lga` VARCHAR,
  `gender` VARCHAR,
  `height` VARCHAR,
  `weight` VARCHAR,
  `blood` VARCHAR,
  `genotype` VARCHAR,
  `id_card_number` VARCHAR,
  `user_role` VARCHAR DEFAULT 0,
  `point_of_care` VARCHAR,
  `sector` VARCHAR,
  `salary_number` VARCHAR,
  `fingerprint` VARCHAR,
  `place_of_work` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `change_providers` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `client_id` INT,
  `previous_health_facility` VARCHAR,
  `new_health_facility` VARCHAR,
  `reason_for_change` VARCHAR,
  `rm_date` DATE,
  `status` VARCHAR,
  `prepared_by` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `agency_id` INT NOT NULL
);

CREATE TABLE `quality_assurances_accreditation_services` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `quality_assurance_id` INT NOT NULL,
  `accreditation_service_id` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `service_drug_sectors` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `name` VARCHAR NOT NULL,
  `drug_id` INT,
  `service_id` INT,
  `price` DOUBLE NOT NULL DEFAULT 0.00,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `wards` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `lg_id` INT NOT NULL,
  `ward_name` VARCHAR NOT NULL,
  `ward_short_name` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `state_id` INT
);

CREATE TABLE `ministry_models` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `name` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `agency_id` INT,
  `previous_ministry_id` BIGINT,
  `type` VARCHAR,
  `hmo_id` BIGINT
);

CREATE TABLE `options` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `quality_assurance_item_id` INT NOT NULL,
  `option_name` VARCHAR NOT NULL,
  `score_value` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `quality_assurance_items` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `form_id` INT,
  `item_name` VARCHAR,
  `response_info` VARCHAR,
  `scores` VARCHAR,
  `remarks` TEXT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `quality_assurance_items_categories_id` INT,
  `quality_assurance_items_sub_categories_id` INT,
  `agency_id` INT NOT NULL,
  `is_scoring` TINYINT NOT NULL DEFAULT 1,
  `item_order` INT
);

CREATE TABLE `local_governments` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `state_id` INT NOT NULL,
  `local_name` VARCHAR NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP,
  `abr` VARCHAR
);

CREATE TABLE `claims_paymentorders` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `claims_id` INT NOT NULL,
  `paymentorder_id` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `data_rows` (
  `id` INT NOT NULL PRIMARY KEY,
  `data_type_id` INT NOT NULL,
  `field` VARCHAR NOT NULL,
  `type` VARCHAR NOT NULL,
  `display_name` VARCHAR NOT NULL,
  `required` TINYINT NOT NULL DEFAULT 0,
  `browse` TINYINT NOT NULL DEFAULT 1,
  `read` TINYINT NOT NULL DEFAULT 1,
  `edit` TINYINT NOT NULL DEFAULT 1,
  `add` TINYINT NOT NULL DEFAULT 1,
  `delete` TINYINT NOT NULL DEFAULT 1,
  `details` TEXT,
  `order` INT NOT NULL DEFAULT 1,
  FOREIGN KEY (`data_type_id`) REFERENCES `data_types`(`id`)
);

CREATE TABLE `drugs_sub_categories` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `category_id` INT,
  `sub_category_name` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `permissions` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `key` VARCHAR NOT NULL,
  `table_name` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `enrollment_users` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `orgenrol_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `migrations` (
  `id` INT NOT NULL PRIMARY KEY,
  `migration` VARCHAR NOT NULL,
  `batch` INT NOT NULL
);

CREATE TABLE `permission_role` (
  `permission_id` BIGINT NOT NULL PRIMARY KEY,
  `role_id` BIGINT NOT NULL PRIMARY KEY,
  FOREIGN KEY (`permission_id`) REFERENCES `permissions`(`id`),
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`)
);

CREATE TABLE `ratings` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `provider_id` BIGINT,
  `service_summary_id` BIGINT,
  `score` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `quality_assurance_items_categories` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT NOT NULL,
  `accreditation_services_id` INT NOT NULL,
  `category_belongs_to` VARCHAR NOT NULL,
  `category_name` VARCHAR NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `is_personnel` TINYINT NOT NULL,
  `form_id` BIGINT NOT NULL DEFAULT 1
);

CREATE TABLE `paymentorders` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `payment_number` VARCHAR NOT NULL,
  `user_id` INT NOT NULL,
  `agency_id` INT NOT NULL,
  `provider_id` INT,
  `letter_of_address` TEXT,
  `type` VARCHAR NOT NULL,
  `status` VARCHAR NOT NULL DEFAULT pending,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `payment_method` VARCHAR NOT NULL DEFAULT offline
);

CREATE TABLE `drug_categories` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `category_name` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `org_enrolls` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT NOT NULL,
  `organization_name` VARCHAR NOT NULL,
  `phone_number` VARCHAR NOT NULL,
  `email` VARCHAR NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `user_id` INT,
  `category` VARCHAR,
  `tpa_id` VARCHAR,
  `org_status` TINYINT NOT NULL DEFAULT 1,
  `previous_hmo_id` BIGINT
);

CREATE TABLE `data_types` (
  `id` INT NOT NULL PRIMARY KEY,
  `name` VARCHAR NOT NULL,
  `slug` VARCHAR NOT NULL,
  `display_name_singular` VARCHAR NOT NULL,
  `display_name_plural` VARCHAR NOT NULL,
  `icon` VARCHAR,
  `model_name` VARCHAR,
  `policy_name` VARCHAR,
  `controller` VARCHAR,
  `description` VARCHAR,
  `generate_permissions` TINYINT NOT NULL DEFAULT 0,
  `server_side` TINYINT NOT NULL DEFAULT 0,
  `details` TEXT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `menu_items` (
  `id` INT NOT NULL PRIMARY KEY,
  `menu_id` INT,
  `title` VARCHAR NOT NULL,
  `url` VARCHAR NOT NULL,
  `target` VARCHAR NOT NULL DEFAULT _self,
  `icon_class` VARCHAR,
  `color` VARCHAR,
  `parent_id` INT,
  `order` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `route` VARCHAR,
  `parameters` TEXT,
  FOREIGN KEY (`menu_id`) REFERENCES `menus`(`id`)
);

CREATE TABLE `authorizationcode_services` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `authorizationcode_id` BIGINT NOT NULL,
  `drug_id` BIGINT,
  `service_id` BIGINT,
  `dose` INT NOT NULL DEFAULT 1,
  `frequency` INT NOT NULL DEFAULT 1,
  `days` INT NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `service_categories` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `category_name` VARCHAR,
  `is_laboratory_test` TINYINT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `remarks` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` INT NOT NULL,
  `agency_id` INT NOT NULL,
  `remark_code` VARCHAR NOT NULL,
  `name` VARCHAR NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `forms` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` BIGINT NOT NULL,
  `name` VARCHAR NOT NULL,
  `description` MEDIUMTEXT,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `fingerprints` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `user_id` INT NOT NULL,
  `leftfour` VARCHAR,
  `rightfour` VARCHAR,
  `thumbs` VARCHAR,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `service_summary_diagnosis` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `service_summary_id` INT NOT NULL,
  `diagnosis_id` INT NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);

CREATE TABLE `accreditation_services` (
  `id` BIGINT NOT NULL PRIMARY KEY,
  `agency_id` INT NOT NULL,
  `service_code` VARCHAR NOT NULL,
  `service_name` VARCHAR NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP
);