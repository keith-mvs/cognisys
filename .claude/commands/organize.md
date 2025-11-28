Organize classified documents into domain-based folder structure.

Steps:
1. Check how many classified documents are waiting to be organized
2. Show sample organization plan (where files will go)
3. Ask user for confirmation:
   - Run dry-run first? (recommended)
   - Organize all or specific documents?
   - Backup originals before moving?
4. Execute file organization using `ifmos.core.file_organizer`
5. Display results:
   - Successfully organized count
   - Failed count
   - New locations for sample files
6. Update database with new file paths

If dry-run, show what would happen without actually moving files.

Present results in a clear table format with before/after paths.
