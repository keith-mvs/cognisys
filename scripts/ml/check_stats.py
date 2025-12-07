#!/usr/bin/env python3
"""Quick stats check for Phase 1 classification results"""

import sqlite3
import sys

def main():
    db_path = 'cognisys/data/training/cognisys_ml.db'

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Total documents
        c.execute('SELECT COUNT(*) FROM documents')
        total = c.fetchone()[0]
        print(f'\nTotal Documents: {total:,}\n')

        # Document type distribution
        c.execute('''
            SELECT document_type, COUNT(*) as cnt
            FROM documents
            GROUP BY document_type
            ORDER BY cnt DESC
            LIMIT 15
        ''')
        results = c.fetchall()

        print('Document Type Distribution:')
        print('=' * 70)
        for doc_type, count in results:
            pct = 100 * count / total
            print(f'{doc_type:45} {count:6,}  ({pct:5.1f}%)')

        # Confidence levels
        c.execute('SELECT COUNT(*) FROM documents WHERE confidence >= 0.90')
        high = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM documents WHERE confidence >= 0.75')
        medium = c.fetchone()[0]

        print(f'\nConfidence Levels:')
        print(f'  High (>=0.90):   {high:6,} / {total:,} ({100*high/total:5.1f}%)')
        print(f'  Medium (>=0.75): {medium:6,} / {total:,} ({100*medium/total:5.1f}%)')

        # Content extraction
        c.execute('SELECT COUNT(*) FROM documents WHERE extracted_text IS NOT NULL AND extracted_text != ""')
        extracted = c.fetchone()[0]

        print(f'\nContent Extraction:')
        print(f'  PDFs with text: {extracted:,} / {total:,} ({100*extracted/total:.1f}%)')

        # Specific classifications (not general_document)
        c.execute('SELECT COUNT(*) FROM documents WHERE document_type != "general_document"')
        specific = c.fetchone()[0]

        print(f'\nClassification Quality:')
        print(f'  Specifically classified: {specific:,} / {total:,} ({100*specific/total:.1f}%)')
        print(f'  General fallback: {total-specific:,} ({100*(total-specific)/total:.1f}%)')

        conn.close()

    except sqlite3.OperationalError as e:
        if 'locked' in str(e):
            print('Database is locked - Phase 1 classification still running...')
            sys.exit(1)
        else:
            raise

if __name__ == '__main__':
    main()
