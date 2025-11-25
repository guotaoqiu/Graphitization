#!/usr/bin/env python3
"""
Upload doped graphite calculation results to MongoDB database
Based on the structure and approach from the user's example script
"""

import os
import json
import pymongo
from pathlib import Path
from datetime import datetime
from tqdm import tqdm


class MongoDBUploader:
    """Upload calculation results to MongoDB database"""

    def __init__(self, mongo_uri, database_name, collection_name):
        """
        Initialize MongoDB connection

        Args:
            mongo_uri: MongoDB connection URI (e.g., 'mongodb://user:pass@host:port/')
            database_name: Name of the database
            collection_name: Name of the collection
        """
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]

        print(f"Connected to MongoDB:")
        print(f"  Database: {database_name}")
        print(f"  Collection: {collection_name}")

    def load_json_data(self, json_file):
        """Load data from JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        print(f"\nLoaded {len(data)} documents from {json_file}")
        return data

    def get_next_id(self):
        """Get next available m_id for the collection"""
        # Get the maximum m_id value
        pipeline = [{"$group": {"_id": None, "max_value": {"$max": "$m_id"}}}]
        result = list(self.collection.aggregate(pipeline))

        if result and result[0]["max_value"] is not None:
            return result[0]["max_value"] + 1
        else:
            return 1

    def upload_documents(self, documents, batch_size=100, overwrite=False):
        """
        Upload documents to MongoDB

        Args:
            documents: List of document dictionaries
            batch_size: Number of documents to insert at once
            overwrite: If True, drop existing collection before upload

        Returns:
            Number of documents successfully uploaded
        """
        print("\n" + "="*70)
        print("Uploading to MongoDB")
        print("="*70)

        # Optionally drop existing collection
        if overwrite:
            print("\nWarning: Overwrite mode enabled")
            response = input("Drop existing collection? (yes/no): ")
            if response.lower() == 'yes':
                self.collection.drop()
                print("Collection dropped")
            else:
                print("Keeping existing collection")

        # Get starting m_id
        start_id = self.get_next_id()
        print(f"\nStarting m_id: {start_id}")

        # Add m_id and update_time to each document
        for i, doc in enumerate(documents):
            doc['m_id'] = start_id + i
            doc['update_time'] = datetime.utcnow()
            doc['update_details'] = 'High-throughput graphite doping study'

            # Add source information
            if 'p_id' not in doc:
                doc['p_id'] = 'graphite_doping_study'

            if 'source_id' not in doc:
                doc['source_id'] = doc.get('job_name', 'unknown')

            if 'substitution_method' not in doc:
                doping_type = doc.get('doping_type')
                if doping_type == 'substitutional':
                    doc['substitution_method'] = 'Substitutional doping'
                elif doping_type == 'interstitial':
                    doc['substitution_method'] = 'Interstitial doping'
                else:
                    doc['substitution_method'] = None

        # Upload in batches
        total_uploaded = 0
        print(f"\nUploading {len(documents)} documents in batches of {batch_size}...")

        for i in tqdm(range(0, len(documents), batch_size)):
            batch = documents[i:i + batch_size]
            try:
                result = self.collection.insert_many(batch, ordered=False)
                total_uploaded += len(result.inserted_ids)
            except pymongo.errors.BulkWriteError as e:
                # Handle duplicate key errors
                total_uploaded += e.details['nInserted']
                print(f"\nWarning: {len(e.details['writeErrors'])} documents had errors")

        print(f"\n✓ Successfully uploaded {total_uploaded} documents")
        return total_uploaded

    def verify_upload(self, expected_count):
        """Verify the upload was successful"""
        print("\n" + "="*70)
        print("Verifying Upload")
        print("="*70)

        # Count documents
        total_count = self.collection.count_documents({})
        print(f"\nTotal documents in collection: {total_count}")

        # Count by doping type
        print("\nDocuments by doping type:")
        pipeline = [
            {"$group": {"_id": "$doping_type", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        for result in self.collection.aggregate(pipeline):
            print(f"  {result['_id']}: {result['count']}")

        # Count by dopant
        print("\nDocuments by dopant element:")
        pipeline = [
            {"$match": {"dopant": {"$ne": None}}},
            {"$group": {"_id": "$dopant", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        for result in self.collection.aggregate(pipeline):
            print(f"  {result['_id']}: {result['count']}")

        print("\n" + "="*70)

    def close(self):
        """Close MongoDB connection"""
        self.client.close()
        print("\nMongoDB connection closed")


def main():
    """Main function"""
    # Configuration - UPDATE THESE VALUES
    MONGO_URI = "mongodb://user:password@localhost:27017/"  # Update with your MongoDB URI
    DATABASE_NAME = "Graphitization"
    COLLECTION_NAME = "Doping"
    JSON_FILE = "../03_analysis/results_database.json"

    print("="*70)
    print("MongoDB Upload - Graphite Doping Results")
    print("="*70)

    # Check if JSON file exists
    if not os.path.exists(JSON_FILE):
        print(f"\nError: JSON file not found: {JSON_FILE}")
        print("Please run 05_export_to_json.py first")
        return

    # Get user confirmation
    print(f"\nMongoDB URI: {MONGO_URI}")
    print(f"Database: {DATABASE_NAME}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Data file: {JSON_FILE}")

    response = input("\nProceed with upload? (yes/no): ")
    if response.lower() != 'yes':
        print("Upload cancelled")
        return

    try:
        # Initialize uploader
        uploader = MongoDBUploader(MONGO_URI, DATABASE_NAME, COLLECTION_NAME)

        # Load data
        documents = uploader.load_json_data(JSON_FILE)

        # Upload documents
        uploaded_count = uploader.upload_documents(documents, batch_size=100, overwrite=False)

        # Verify upload
        uploader.verify_upload(uploaded_count)

        # Close connection
        uploader.close()

        print("\n" + "="*70)
        print("Upload Complete!")
        print("="*70)

    except pymongo.errors.ConnectionFailure as e:
        print(f"\nError: Could not connect to MongoDB: {e}")
        print("Please check your MongoDB connection settings")
    except Exception as e:
        print(f"\nError during upload: {e}")
        raise


if __name__ == "__main__":
    # Print usage instructions
    print("\n" + "="*70)
    print("IMPORTANT: Update MongoDB connection settings before running!")
    print("="*70)
    print("\nEdit this file and update:")
    print("  - MONGO_URI: Your MongoDB connection string")
    print("  - DATABASE_NAME: Target database name")
    print("  - COLLECTION_NAME: Target collection name")
    print("\nExample:")
    print("  MONGO_URI = 'mongodb://username:password@host:port/'")
    print("="*70)
    print()

    main()
