#!/usr/bin/env python3
"""
Reclassify Unknown Files
Uses enhanced pattern matching and context-aware rules
"""

import sqlite3
from pathlib import Path
import re


class UnknownFileReclassifier:
    """Reclassify files marked as 'unknown' using enhanced rules"""

    def __init__(self, db_path: str = '.ifmos/file_registry.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.stats = {
            'total': 0,
            'reclassified': 0,
            'still_unknown': 0
        }

    def classify_by_context(self, filepath: Path) -> tuple:
        """
        Context-aware classification using filename + extension
        Returns: (document_type, confidence, method)
        """
        filename = filepath.name.lower()
        stem = filepath.stem.lower()
        ext = filepath.suffix.lower()

        # PDF - Context-based
        if ext == '.pdf':
            if 'paystub' in filename or 'paycheck' in filename:
                return ('financial_document', 0.95, 'context_filename')
            elif 'invoice' in filename or 'receipt' in filename:
                return ('financial_invoice', 0.95, 'context_filename')
            elif 'report' in filename:
                return ('technical_documentation', 0.85, 'context_filename')
            elif any(x in filename for x in ['manual', 'guide', 'tutorial']):
                return ('technical_documentation', 0.85, 'context_filename')
            elif any(x in filename for x in ['yoga', 'exercise', 'health', 'fitness']):
                return ('personal_health', 0.90, 'context_filename')
            elif 'keyboard' in filename or 'shortcut' in filename:
                return ('technical_documentation', 0.85, 'context_filename')
            else:
                return ('document_pdf', 0.70, 'pattern_extension')

        # Images - By extension
        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp', '.gif', '.tiff']:
            if 'screenshot' in filename or 'screen' in filename:
                return ('media_screenshot', 0.85, 'context_filename')
            elif 'photo' in filename or 'img_' in filename or re.match(r'img_\d+', filename):
                return ('media_photo', 0.85, 'context_filename')
            else:
                return ('media_image', 0.80, 'pattern_extension')

        # Design/Vector files
        if ext in ['.eps', '.ai', '.svg']:
            if 'logo' in filename or 'icon' in filename:
                return ('design_logo', 0.90, 'context_filename')
            else:
                return ('design_vector', 0.85, 'pattern_extension')

        # Photoshop
        if ext == '.psd':
            return ('design_photoshop', 0.90, 'pattern_extension')

        # Documents
        if ext in ['.docx', '.doc']:
            if any(x in filename for x in ['yoga', 'exercise', 'health']):
                return ('personal_health', 0.90, 'context_filename')
            elif 'resume' in filename or 'cv' in filename:
                return ('personal_career', 0.95, 'context_filename')
            else:
                return ('document_word', 0.75, 'pattern_extension')

        # Web files
        if ext in ['.html', '.htm']:
            return ('web_page', 0.85, 'pattern_extension')
        if ext == '.css':
            return ('web_stylesheet', 0.90, 'pattern_extension')
        if ext == '.js':
            return ('technical_script', 0.85, 'pattern_extension')

        # Fonts
        if ext in ['.ttf', '.otf', '.woff', '.woff2', '.eot']:
            return ('web_font', 0.95, 'pattern_extension')

        # Logs
        if ext == '.log' or 'log' in filename:
            return ('technical_log', 0.90, 'pattern_extension')

        # Text files with context
        if ext == '.txt':
            if 'readme' in filename:
                return ('technical_documentation', 0.85, 'context_filename')
            elif 'license' in filename:
                return ('technical_documentation', 0.85, 'context_filename')
            elif 'report' in filename:
                return ('technical_log', 0.75, 'context_filename')
            else:
                return ('document_text', 0.70, 'pattern_extension')

        # Archives
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']:
            return ('archive', 0.90, 'pattern_extension')

        # Video
        if ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']:
            return ('media_video', 0.90, 'pattern_extension')

        # Audio
        if ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
            return ('media_audio', 0.90, 'pattern_extension')

        # Minecraft region files
        if ext == '.mrf' or ext == '.mcr':
            return ('game_data', 0.85, 'pattern_extension')

        # Database files
        if ext in ['.db', '.sqlite', '.sqlite3', '.mdb']:
            return ('technical_database', 0.90, 'pattern_extension')

        # Spreadsheets
        if ext in ['.xlsx', '.xls', '.ods']:
            if 'budget' in filename or 'financial' in filename:
                return ('financial_spreadsheet', 0.90, 'context_filename')
            else:
                return ('business_spreadsheet', 0.80, 'pattern_extension')

        # Presentations
        if ext in ['.pptx', '.ppt', '.odp']:
            return ('business_presentation', 0.85, 'pattern_extension')

        # CAD files
        if ext in ['.prt', '.sldprt', '.dwg', '.dxf']:
            return ('cad_model', 0.90, 'pattern_extension')

        return (None, 0.0, None)

    def reclassify_unknown(self):
        """Reclassify all unknown files"""
        print("\n" + "=" * 80)
        print("RECLASSIFYING UNKNOWN FILES")
        print("=" * 80)

        # Get all unknown files
        self.cursor.execute('''
            SELECT file_id, original_path
            FROM file_registry
            WHERE document_type = 'unknown'
        ''')

        unknown_files = self.cursor.fetchall()
        self.stats['total'] = len(unknown_files)

        print(f"\nFound {self.stats['total']:,} unknown files")
        print()

        # Reclassify
        updates = []
        batch_size = 100

        for i, (file_id, path) in enumerate(unknown_files, 1):
            if i % batch_size == 0:
                print(f"  Progress: {i:,}/{self.stats['total']:,} ({i/self.stats['total']*100:.1f}%)")

            filepath = Path(path)
            doc_type, confidence, method = self.classify_by_context(filepath)

            if doc_type:
                updates.append((
                    doc_type,
                    confidence,
                    method,
                    file_id
                ))
                self.stats['reclassified'] += 1
            else:
                self.stats['still_unknown'] += 1

        # Batch update
        if updates:
            self.cursor.executemany('''
                UPDATE file_registry
                SET document_type = ?,
                    confidence = ?,
                    classification_method = ?,
                    updated_at = datetime('now')
                WHERE file_id = ?
            ''', updates)

            self.conn.commit()

        # Summary
        print()
        print("=" * 80)
        print("RECLASSIFICATION COMPLETE")
        print("=" * 80)
        print(f"Total unknown files: {self.stats['total']:,}")
        print(f"Reclassified: {self.stats['reclassified']:,} ({self.stats['reclassified']/self.stats['total']*100:.1f}%)")
        print(f"Still unknown: {self.stats['still_unknown']:,} ({self.stats['still_unknown']/self.stats['total']*100:.1f}%)")

        # Calculate new unknown rate
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type = "unknown"')
        remaining_unknown = self.cursor.fetchone()[0]

        new_unknown_rate = (remaining_unknown / total_files * 100) if total_files > 0 else 0

        print(f"\nNew unknown rate: {new_unknown_rate:.2f}% (was 11.19%)")
        print("=" * 80)

        return self.stats

    def show_reclassification_breakdown(self):
        """Show breakdown of reclassified files"""
        print("\n" + "=" * 80)
        print("RECLASSIFICATION BREAKDOWN")
        print("=" * 80)

        self.cursor.execute('''
            SELECT classification_method, COUNT(*) as count
            FROM file_registry
            WHERE classification_method IN ('context_filename', 'pattern_extension')
              AND updated_at > datetime('now', '-1 hour')
            GROUP BY classification_method
            ORDER BY count DESC
        ''')

        print("\nBy method:")
        for method, count in self.cursor.fetchall():
            print(f"  {method}: {count:,}")

        self.cursor.execute('''
            SELECT document_type, COUNT(*) as count
            FROM file_registry
            WHERE classification_method IN ('context_filename', 'pattern_extension')
              AND updated_at > datetime('now', '-1 hour')
            GROUP BY document_type
            ORDER BY count DESC
            LIMIT 15
        ''')

        print("\nTop 15 new categories:")
        for doc_type, count in self.cursor.fetchall():
            print(f"  {doc_type}: {count:,}")

        print("=" * 80)

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    print("=" * 80)
    print("UNKNOWN FILE RECLASSIFICATION")
    print("=" * 80)

    reclassifier = UnknownFileReclassifier()

    try:
        # Reclassify
        stats = reclassifier.reclassify_unknown()

        # Show breakdown
        if stats['reclassified'] > 0:
            reclassifier.show_reclassification_breakdown()

        print("\n" + "=" * 80)
        print("SUCCESS")
        print("=" * 80)
        print(f"Reclassified {stats['reclassified']:,} files")
        print(f"Unknown rate reduced from 11.19%")

    finally:
        reclassifier.close()


if __name__ == '__main__':
    main()
