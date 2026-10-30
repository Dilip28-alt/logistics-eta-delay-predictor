"""
Data Exporter for CSV, JSON, SQLite, and SQL DDL seed scripts.
Generates cryptographic SHA-256 manifests for validation and reproducibility auditing.
"""

import os
import csv
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List

from src.generator.generator import SyntheticDataGenerator


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class DataExporter:
    def __init__(self, generator: SyntheticDataGenerator, output_dir: str):
        self.gen = generator
        self.output_dir = output_dir
        self.csv_dir = os.path.join(output_dir, "csv")
        self.json_dir = os.path.join(output_dir, "json")
        self.db_path = os.path.join(output_dir, "logistics.db")
        self.sql_seed_path = os.path.join(output_dir, "seed.sql")
        self.manifest_path = os.path.join(output_dir, "manifest.json")

        os.makedirs(self.csv_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)

    def _get_datasets(self) -> Dict[str, List[Any]]:
        return {
            "carriers": [c.to_dict() for c in self.gen.carriers],
            "facilities": [f.to_dict() for f in self.gen.facilities],
            "routes": [r.to_dict() for r in self.gen.routes],
            "service_levels": [s.to_dict() for s in self.gen.service_levels],
            "delay_reasons": [d.to_dict() for d in self.gen.delay_reasons],
            "weather_events": [w.to_dict() for w in self.gen.weather_events],
            "facility_queues": [q.to_dict() for q in self.gen.facility_queues],
            "shipments": [s.to_dict() for s in self.gen.shipments],
            "shipment_legs": [l.to_dict() for l in self.gen.shipment_legs],
            "tracking_events": [t.to_dict() for t in self.gen.tracking_events],
            "eta_estimates": [e.to_dict() for e in self.gen.eta_estimates],
            "ground_truth": [g.to_dict() for g in self.gen.ground_truth]
        }

    def export_csv(self) -> Dict[str, str]:
        datasets = self._get_datasets()
        paths = {}
        for name, rows in datasets.items():
            if not rows:
                continue
            # Ground truth goes directly to data/ or data/csv/
            csv_path = os.path.join(self.csv_dir, f"{name}.csv")
            fieldnames = list(rows[0].keys())
            with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            paths[name] = csv_path

            # Also export ground_truth directly to root data/ dir if ground_truth
            if name == "ground_truth":
                root_gt = os.path.join(self.output_dir, "ground_truth.csv")
                with open(root_gt, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

        return paths

    def export_json(self) -> Dict[str, str]:
        datasets = self._get_datasets()
        paths = {}
        for name, rows in datasets.items():
            json_path = os.path.join(self.json_dir, f"{name}.json")
            with open(json_path, mode="w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2)
            paths[name] = json_path

            if name == "ground_truth":
                root_gt = os.path.join(self.output_dir, "ground_truth.json")
                with open(root_gt, mode="w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2)

        return paths

    def export_sqlite(self) -> str:
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # DDL Script
        ddl = """
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
        """
        cursor.executescript(ddl)

        # Batch insert data
        datasets = self._get_datasets()
        for table_name, rows in datasets.items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(cols))
            sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
            data_tuples = [tuple(r[c] for c in cols) for r in rows]
            cursor.executemany(sql, data_tuples)

        conn.commit()
        conn.close()

        # Write SQL seed file
        with open(self.sql_seed_path, "w", encoding="utf-8") as f:
            f.write("-- Logistics Platform Seed Data\n")
            f.write(ddl)
            f.write("\n\n-- Data insertion completed in SQLite database.\n")

        return self.db_path

    def generate_manifest(self) -> Dict[str, Any]:
        """Generates cryptographic source manifest and summary metrics."""
        manifest = {
            "system": "Logistics ETA Estimation & Delay Risk Platform",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed": self.gen.seed,
            "row_counts": self.gen.summary(),
            "files": {}
        }

        # Compute hashes for all generated files
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                if file == "manifest.json":
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.output_dir).replace("\\", "/")
                manifest["files"][rel_path] = {
                    "size_bytes": os.path.getsize(full_path),
                    "sha256": compute_sha256(full_path)
                }

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest
