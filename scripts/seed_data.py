"""
=============================================================================
Seed Data — Populate the database with initial data for development
=============================================================================
Usage:
    python scripts/seed_data.py [--users] [--documents] [--golden-dataset] [--all]
"""
import argparse
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


def seed_users():
    """Create default users: admin, hr_manager, engineer."""
    print("Seeding users...")
    # TODO: Implement in Stage 4 (Auth system)
    print("  (skipped — auth system not yet implemented)")


def seed_documents():
    """Upload sample documents from data/sample_docs/."""
    print("Seeding sample documents...")
    sample_dir = Path(__file__).resolve().parent.parent / "backend" / "data" / "sample_docs"
    # TODO: Implement in Stage 1 (Document upload)
    print(f"  (skipped — document upload not yet implemented; files in {sample_dir})")


def seed_golden_dataset():
    """Load and validate Golden Dataset Q&A pairs."""
    print("Seeding Golden Dataset...")
    dataset_path = (
        Path(__file__).resolve().parent.parent
        / "backend"
        / "data"
        / "golden_dataset"
        / "qa_pairs.json"
    )
    if dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} Q&A pairs.")
    else:
        print(f"  Dataset file not found: {dataset_path}")


def main():
    parser = argparse.ArgumentParser(description="Seed database with initial data")
    parser.add_argument("--users", action="store_true", help="Seed default users")
    parser.add_argument("--documents", action="store_true", help="Seed sample documents")
    parser.add_argument("--golden-dataset", action="store_true", help="Seed Golden Dataset")
    parser.add_argument("--all", action="store_true", help="Seed everything")
    args = parser.parse_args()

    seed_all = args.all

    print("=" * 50)
    print("  Enterprise RAG Agent — Seed Data")
    print("=" * 50)

    if seed_all or args.users:
        seed_users()
    if seed_all or args.documents:
        seed_documents()
    if seed_all or args.golden_dataset:
        seed_golden_dataset()

    print("\nDone.")


if __name__ == "__main__":
    main()
