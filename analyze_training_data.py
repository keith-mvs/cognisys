import sqlite3
conn = sqlite3.connect('.ifmos/file_registry.db')
cursor = conn.cursor()

# Count files by classification method
cursor.execute('''
    SELECT classification_method, COUNT(*) as count,
           AVG(confidence) as avg_conf
    FROM file_registry
    WHERE canonical_state != 'deleted'
      AND classification_method IS NOT NULL
    GROUP BY classification_method
    ORDER BY count DESC
''')

print('Classification Method     | Count    | Avg Conf')
print('-' * 55)
for method, count, conf in cursor.fetchall():
    conf_val = conf if conf else 0
    print(f'{method:25} | {count:8,} | {conf_val:6.1%}')

print('\n')

# Check for existing training data CSV
from pathlib import Path
csv_path = Path('.ifmos/training_data.csv')
if csv_path.exists():
    import pandas as pd
    df = pd.read_csv(csv_path)
    print(f'Existing training CSV: {len(df):,} samples')
else:
    print('No existing training CSV found')

conn.close()
