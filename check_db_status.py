import sqlite3

conn = sqlite3.connect('.ifmos/file_registry.db')

print("=" * 60)
print("IFMOS Database Status")
print("=" * 60)

# Check schema first
print("\nDatabase Schema:")
print("\nTables:")
for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(f"  - {row[0]}")

# Get file_registry columns
print("\nfile_registry columns:")
for row in conn.execute("PRAGMA table_info(file_registry)"):
    print(f"  - {row[1]} ({row[2]})")

# Total records
total = conn.execute('SELECT COUNT(*) FROM file_registry').fetchone()[0]
print(f"\nTotal records: {total}")

# Files by canonical_state
print("\nFiles by canonical_state:")
for row in conn.execute('SELECT canonical_state, COUNT(*) FROM file_registry GROUP BY canonical_state ORDER BY COUNT(*) DESC'):
    state = row[0] if row[0] else 'NULL'
    print(f"  {state:15} {row[1]:6}")

# Files by document_type
print("\nFiles by document_type (top 15):")
for row in conn.execute('SELECT document_type, COUNT(*) FROM file_registry GROUP BY document_type ORDER BY COUNT(*) DESC LIMIT 15'):
    dtype = row[0] if row[0] else 'NULL'
    print(f"  {dtype:35} {row[1]:6}")

# Classification method breakdown
print("\nClassification method:")
for row in conn.execute('SELECT classification_method, COUNT(*) FROM file_registry GROUP BY classification_method ORDER BY COUNT(*) DESC'):
    method = row[0] if row[0] else 'NULL'
    print(f"  {method:15} {row[1]:6}")

# Duplicates
duplicates = conn.execute('SELECT COUNT(*) FROM file_registry WHERE is_duplicate=1').fetchone()[0]
print(f"\nDuplicates identified: {duplicates}")

# Files requiring review
review = conn.execute('SELECT COUNT(*) FROM file_registry WHERE requires_review=1').fetchone()[0]
print(f"Files requiring review: {review}")

# Missing files
missing = conn.execute('SELECT COUNT(*) FROM file_registry WHERE is_missing=1').fetchone()[0]
print(f"Missing files: {missing}")

conn.close()
print("\n" + "=" * 60)
