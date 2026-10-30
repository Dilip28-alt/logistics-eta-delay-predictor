-- Logistics Platform Seed Data

        CREATE TABLE carriers (
            carrier_id TEXT PRIMARY KEY,
            carrier_name TEXT NOT NULL,
            transport_mode TEXT NOT NULL,
            reliability_score REAL NOT NULL,
            operating_calendar TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE facilities (
            facility_id TEXT PRIMARY KEY,
            facility_name TEXT NOT NULL,
            facility_type TEXT NOT NULL,
            region TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            capacity_trucks_per_hr INTEGER NOT NULL,
            nominal_dwell_hours REAL NOT NULL,
            operating_calendar TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE routes (
            route_id TEXT PRIMARY KEY,
            origin_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            destination_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            primary_carrier_id TEXT NOT NULL REFERENCES carriers(carrier_id),
            transport_mode TEXT NOT NULL,
            distance_km REAL NOT NULL,
            standard_transit_hours REAL NOT NULL,
            is_toll_road BOOLEAN NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE service_levels (
            service_level_id TEXT PRIMARY KEY,
            service_level_name TEXT NOT NULL,
            max_delay_tolerance_mins INTEGER NOT NULL,
            target_on_time_pct REAL NOT NULL,
            penalty_per_hour_delayed REAL NOT NULL,
            description TEXT
        );

        CREATE TABLE delay_reasons (
            delay_reason_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            sub_reason TEXT NOT NULL,
            severity_tier TEXT NOT NULL,
            is_carrier_fault BOOLEAN NOT NULL
        );

        CREATE TABLE weather_events (
            weather_id TEXT PRIMARY KEY,
            region TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            start_ts TEXT NOT NULL,
            end_ts TEXT NOT NULL,
            delay_multiplier REAL NOT NULL,
            radius_km REAL NOT NULL,
            center_lat REAL NOT NULL,
            center_lon REAL NOT NULL
        );

        CREATE TABLE facility_queues (
            queue_id TEXT PRIMARY KEY,
            facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            snapshot_ts TEXT NOT NULL,
            queue_depth_trucks INTEGER NOT NULL,
            avg_dwell_hours REAL NOT NULL,
            active_berths INTEGER NOT NULL,
            inflow_rate_per_hr REAL NOT NULL,
            outflow_rate_per_hr REAL NOT NULL,
            congestion_level TEXT NOT NULL
        );

        CREATE TABLE shipments (
            shipment_id TEXT PRIMARY KEY,
            origin_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            destination_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            service_level_id TEXT NOT NULL REFERENCES service_levels(service_level_id),
            total_legs INTEGER NOT NULL,
            planned_departure_ts TEXT NOT NULL,
            planned_delivery_ts TEXT NOT NULL,
            actual_departure_ts TEXT,
            actual_delivery_ts TEXT,
            current_status TEXT NOT NULL,
            total_weight_kg REAL NOT NULL,
            cargo_value_usd REAL NOT NULL,
            final_delay_minutes INTEGER NOT NULL,
            is_delayed BOOLEAN NOT NULL,
            primary_delay_reason_id TEXT REFERENCES delay_reasons(delay_reason_id),
            created_at TEXT NOT NULL
        );

        CREATE TABLE shipment_legs (
            leg_id TEXT PRIMARY KEY,
            shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
            leg_sequence INTEGER NOT NULL,
            origin_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            destination_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
            carrier_id TEXT NOT NULL REFERENCES carriers(carrier_id),
            route_id TEXT NOT NULL REFERENCES routes(route_id),
            planned_leg_start_ts TEXT NOT NULL,
            planned_leg_end_ts TEXT NOT NULL,
            actual_leg_start_ts TEXT,
            actual_leg_end_ts TEXT,
            leg_distance_km REAL NOT NULL,
            leg_status TEXT NOT NULL
        );

        CREATE TABLE tracking_events (
            event_id TEXT PRIMARY KEY,
            shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
            leg_id TEXT REFERENCES shipment_legs(leg_id),
            event_sequence INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            ingestion_timestamp TEXT NOT NULL,
            facility_id TEXT REFERENCES facilities(facility_id),
            latitude REAL,
            longitude REAL,
            status_code TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE eta_estimates (
            eta_id TEXT PRIMARY KEY,
            shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
            prediction_ts TEXT NOT NULL,
            current_leg_sequence INTEGER NOT NULL,
            elapsed_transit_hours REAL NOT NULL,
            remaining_distance_km REAL NOT NULL,
            predicted_delivery_ts TEXT NOT NULL,
            confidence_p10_ts TEXT NOT NULL,
            confidence_p90_ts TEXT NOT NULL,
            predicted_delay_minutes INTEGER NOT NULL,
            delay_risk_level TEXT NOT NULL,
            predicted_delay_reason_id TEXT REFERENCES delay_reasons(delay_reason_id),
            model_version TEXT NOT NULL,
            features_snapshot_json TEXT NOT NULL
        );

        CREATE TABLE ground_truth (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            is_anomaly BOOLEAN NOT NULL,
            expected_decision TEXT NOT NULL,
            ground_truth_delivery_ts TEXT,
            ground_truth_delay_mins INTEGER,
            ground_truth_delay_category TEXT,
            anomaly_details TEXT
        );

        CREATE INDEX idx_shipments_status ON shipments(current_status);
        CREATE INDEX idx_shipments_delayed ON shipments(is_delayed);
        CREATE INDEX idx_tracking_events_shipment ON tracking_events(shipment_id);
        CREATE INDEX idx_facility_queues_fac ON facility_queues(facility_id);
        CREATE INDEX idx_eta_shipment ON eta_estimates(shipment_id);
        

-- Data insertion completed in SQLite database.
