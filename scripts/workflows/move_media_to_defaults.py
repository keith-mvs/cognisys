#!/usr/bin/env python3
r"""
CogniSys Media Files Migration
Moves image and video files to Windows default locations
- Images (.jpg, .png, .jpeg, etc.) -> C:\Users\kjfle\Pictures
- Videos (.mov, .mp4, etc.) -> C:\Users\kjfle\Videos
"""

import sqlite3
import os
import shutil
from pathlib import Path
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MediaMigrator:
    """Migrates media files to Windows default locations"""

    def __init__(self, db_path: str, pictures_dir: str, videos_dir: str):
        self.db_path = db_path
        self.pictures_dir = pictures_dir
        self.videos_dir = videos_dir
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Image extensions
        self.image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
            '.webp', '.svg', '.ico', '.heic', '.heif', '.raw', '.cr2',
            '.nef', '.dng', '.arw'
        }

        # Video extensions
        self.video_extensions = {
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',
            '.m4v', '.mpg', '.mpeg', '.3gp', '.3g2', '.mts', '.m2ts',
            '.vob', '.ogv', '.f4v'
        }

    def _is_image(self, filename: str) -> bool:
        """Check if file is an image"""
        ext = Path(filename).suffix.lower()
        return ext in self.image_extensions

    def _is_video(self, filename: str) -> bool:
        """Check if file is a video"""
        ext = Path(filename).suffix.lower()
        return ext in self.video_extensions

    def migrate_media(self, dry_run: bool = True) -> dict:
        """Migrate all media files to default locations"""

        logger.info("=" * 80)
        logger.info("MEDIA FILES MIGRATION")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        logger.info("")
        logger.info(f"Pictures destination: {self.pictures_dir}")
        logger.info(f"Videos destination: {self.videos_dir}")
        logger.info("")

        # Get all files from Organized_V2
        self.cursor.execute("""
            SELECT id, file_name, file_path, document_type
            FROM documents
            WHERE file_path LIKE '%Organized_V2%'
            ORDER BY file_name
        """)

        all_files = self.cursor.fetchall()

        # Categorize files
        images = []
        videos = []

        for doc_id, filename, filepath, doc_type in all_files:
            if self._is_image(filename):
                images.append({
                    'id': doc_id,
                    'filename': filename,
                    'old_path': filepath,
                    'doc_type': doc_type
                })
            elif self._is_video(filename):
                videos.append({
                    'id': doc_id,
                    'filename': filename,
                    'old_path': filepath,
                    'doc_type': doc_type
                })

        logger.info(f"Total files in Organized_V2: {len(all_files)}")
        logger.info(f"  Images to move: {len(images)}")
        logger.info(f"  Videos to move: {len(videos)}")
        logger.info(f"  Documents (staying): {len(all_files) - len(images) - len(videos)}")
        logger.info("")

        stats = {
            'total_files': len(all_files),
            'images': {
                'total': len(images),
                'moved': 0,
                'skipped': 0,
                'errors': 0,
                'by_extension': defaultdict(int)
            },
            'videos': {
                'total': len(videos),
                'moved': 0,
                'skipped': 0,
                'errors': 0,
                'by_extension': defaultdict(int)
            }
        }

        # Process images
        if images:
            logger.info("=" * 80)
            logger.info(f"PROCESSING IMAGES ({len(images)} files)")
            logger.info("=" * 80)

            for item in images:
                ext = Path(item['filename']).suffix.lower()
                stats['images']['by_extension'][ext] += 1

                # Generate new path
                new_path = os.path.join(self.pictures_dir, item['filename'])

                # Handle duplicates
                if os.path.exists(new_path):
                    base, extension = os.path.splitext(item['filename'])
                    counter = 1
                    while os.path.exists(new_path):
                        new_filename = f"{base}_{counter}{extension}"
                        new_path = os.path.join(self.pictures_dir, new_filename)
                        counter += 1
                    logger.debug(f"Renamed to avoid collision: {new_filename}")

                if not dry_run:
                    try:
                        # Ensure destination directory exists
                        os.makedirs(self.pictures_dir, exist_ok=True)

                        # Move file
                        shutil.move(item['old_path'], new_path)

                        # Update database
                        self.cursor.execute("""
                            UPDATE documents
                            SET file_path = ?
                            WHERE id = ?
                        """, (new_path, item['id']))

                        stats['images']['moved'] += 1

                        if stats['images']['moved'] % 10 == 0:
                            logger.info(f"  Moved {stats['images']['moved']}/{len(images)} images...")

                    except Exception as e:
                        logger.error(f"Error moving {item['filename']}: {e}")
                        stats['images']['errors'] += 1
                else:
                    stats['images']['moved'] += 1

            logger.info(f"✓ Images processed: {stats['images']['moved']}/{len(images)}")
            logger.info("")

        # Process videos
        if videos:
            logger.info("=" * 80)
            logger.info(f"PROCESSING VIDEOS ({len(videos)} files)")
            logger.info("=" * 80)

            for item in videos:
                ext = Path(item['filename']).suffix.lower()
                stats['videos']['by_extension'][ext] += 1

                # Generate new path
                new_path = os.path.join(self.videos_dir, item['filename'])

                # Handle duplicates
                if os.path.exists(new_path):
                    base, extension = os.path.splitext(item['filename'])
                    counter = 1
                    while os.path.exists(new_path):
                        new_filename = f"{base}_{counter}{extension}"
                        new_path = os.path.join(self.videos_dir, new_filename)
                        counter += 1
                    logger.debug(f"Renamed to avoid collision: {new_filename}")

                if not dry_run:
                    try:
                        # Ensure destination directory exists
                        os.makedirs(self.videos_dir, exist_ok=True)

                        # Move file
                        shutil.move(item['old_path'], new_path)

                        # Update database
                        self.cursor.execute("""
                            UPDATE documents
                            SET file_path = ?
                            WHERE id = ?
                        """, (new_path, item['id']))

                        stats['videos']['moved'] += 1

                        if stats['videos']['moved'] % 10 == 0:
                            logger.info(f"  Moved {stats['videos']['moved']}/{len(videos)} videos...")

                    except Exception as e:
                        logger.error(f"Error moving {item['filename']}: {e}")
                        stats['videos']['errors'] += 1
                else:
                    stats['videos']['moved'] += 1

            logger.info(f"✓ Videos processed: {stats['videos']['moved']}/{len(videos)}")
            logger.info("")

        if not dry_run:
            self.conn.commit()

        # Print summary
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)

        if stats['images']['total'] > 0:
            logger.info(f"IMAGES:")
            logger.info(f"  Total: {stats['images']['total']}")
            logger.info(f"  Moved: {stats['images']['moved']}")
            logger.info(f"  Errors: {stats['images']['errors']}")
            logger.info(f"  Destination: {self.pictures_dir}")

            if stats['images']['by_extension']:
                logger.info(f"  By extension:")
                for ext, count in sorted(stats['images']['by_extension'].items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"    {ext:10} {count:5} files")
            logger.info("")

        if stats['videos']['total'] > 0:
            logger.info(f"VIDEOS:")
            logger.info(f"  Total: {stats['videos']['total']}")
            logger.info(f"  Moved: {stats['videos']['moved']}")
            logger.info(f"  Errors: {stats['videos']['errors']}")
            logger.info(f"  Destination: {self.videos_dir}")

            if stats['videos']['by_extension']:
                logger.info(f"  By extension:")
                for ext, count in sorted(stats['videos']['by_extension'].items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"    {ext:10} {count:5} files")
            logger.info("")

        logger.info(f"Documents remaining in Organized_V2: {len(all_files) - len(images) - len(videos)}")
        logger.info("")

        if dry_run:
            logger.info("[DRY RUN] No files moved")
            logger.info("Run with --execute to move files")
        else:
            logger.info("✓ Migration complete!")
            logger.info(f"  Total moved: {stats['images']['moved'] + stats['videos']['moved']}")
            logger.info(f"  Total errors: {stats['images']['errors'] + stats['videos']['errors']}")

        return stats

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Move media files to Windows default locations")
    parser.add_argument('--db', type=str, default='cognisys/data/training/cognisys_ml.db')
    parser.add_argument('--pictures', type=str, default='C:/Users/kjfle/Pictures',
                        help='Destination for image files')
    parser.add_argument('--videos', type=str, default='C:/Users/kjfle/Videos',
                        help='Destination for video files')
    parser.add_argument('--execute', action='store_true',
                        help='Execute migration (default is dry-run)')

    args = parser.parse_args()

    migrator = MediaMigrator(args.db, args.pictures, args.videos)
    try:
        stats = migrator.migrate_media(dry_run=not args.execute)
    finally:
        migrator.close()
