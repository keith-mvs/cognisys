import sqlite3

conn = sqlite3.connect('ifmos/data/training/ifmos_ml.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'")
schema = cursor.fetchone()

print("=" * 80)
print("IFMOS DATABASE SCHEMA - Documents Table")
print("=" * 80)
if schema:
    print(schema[0])
else:
    print("Table not found")

print("\n" + "=" * 80)
print("SAMPLE DOCUMENT-TO-FILE LINKS")
print("=" * 80)

# Get sample records
cursor.execute('''
    SELECT id, file_name, file_path, document_type, confidence, processing_timestamp
    FROM documents
    ORDER BY id DESC
    LIMIT 5
''')

for row in cursor.fetchall():
    print(f"\nDocument ID: {row[0]}")
    conf = row[4] if row[4] is not None else 0.0
    print(f"  Type: {row[3]} (confidence: {conf:.2f})")
    print(f"  Filename: {row[1]}")
    print(f"  Full Path: {row[2]}")
    print(f"  Classified: {row[5]}")

# Count total documents
cursor.execute("SELECT COUNT(*), COUNT(DISTINCT file_path) FROM documents")
total, unique_paths = cursor.fetchone()

print("\n" + "=" * 80)
print(f"Total Documents: {total}")
print(f"Unique File Paths: {unique_paths}")
print("=" * 80)

conn.close()
